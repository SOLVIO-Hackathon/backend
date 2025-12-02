"""
Behavioral fraud detection service for analyzing collector patterns.
"""

from typing import List, Dict, Optional, Tuple
from uuid import UUID
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_X, ST_Y
import pygeohash as geohash

from app.models.user import User
from app.models.quest import Quest, QuestStatus
from app.models.collector_behavior import CollectorBehaviorPattern
from app.core.config import settings


class FraudDetectionService:
    """Analyze collector behavior patterns for fraud detection"""

    # Fraud detection thresholds
    ANALYSIS_WINDOW_DAYS = 7  # Analyze last 7 days
    SUSPICIOUS_COMPLETION_TIME_MINUTES = 5  # Impossibly fast
    MAX_QUESTS_PER_HOUR_THRESHOLD = 5  # Suspiciously high frequency
    LOCATION_CLUSTER_THRESHOLD_METERS = 100  # Same spot repeatedly
    MIN_QUESTS_FOR_ANALYSIS = 3  # Need minimum data

    # Risk scoring weights
    WEIGHT_RAPID_COMPLETIONS = 0.25
    WEIGHT_LOCATION_CLUSTERING = 0.30
    WEIGHT_HIGH_FREQUENCY = 0.20
    WEIGHT_REJECTION_RATE = 0.25

    async def analyze_collector_behavior(
        self, collector_id: UUID, session: AsyncSession
    ) -> CollectorBehaviorPattern:
        """
        Analyze a collector's recent behavior and calculate fraud risk score.

        Returns:
            CollectorBehaviorPattern with calculated metrics and risk score
        """
        window_start = datetime.utcnow() - timedelta(days=self.ANALYSIS_WINDOW_DAYS)
        window_end = datetime.utcnow()

        # Fetch collector's recent completed quests
        query = (
            select(Quest)
            .where(
                and_(
                    Quest.collector_id == collector_id,
                    Quest.status.in_([QuestStatus.VERIFIED, QuestStatus.REJECTED]),
                    Quest.completed_at >= window_start,
                )
            )
            .order_by(Quest.completed_at)
        )

        result = await session.execute(query)
        quests = result.scalars().all()

        if len(quests) < self.MIN_QUESTS_FOR_ANALYSIS:
            # Insufficient data - return neutral profile
            return self._create_neutral_pattern(collector_id, window_start, window_end)

        # Analyze patterns
        timing_analysis = await self._analyze_timing_patterns(quests, session)
        location_analysis = await self._analyze_location_patterns(quests, session)
        frequency_analysis = self._analyze_frequency_patterns(quests)
        rejection_analysis = self._analyze_rejection_rate(quests)

        # Calculate fraud indicators
        fraud_flags = {}
        fraud_scores = []

        # 1. Rapid completions (suspiciously fast)
        if timing_analysis["suspicious_rapid_count"] > 0:
            fraud_flags["impossible_timing"] = timing_analysis["suspicious_rapid_count"]
            rapid_score = min(
                timing_analysis["suspicious_rapid_count"] / len(quests), 1.0
            )
            fraud_scores.append(rapid_score * self.WEIGHT_RAPID_COMPLETIONS)

        # 2. Location clustering (same spot repeatedly)
        if location_analysis["max_density"] > 10:  # >10 quests/km²
            fraud_flags["location_clustering"] = location_analysis["max_density"]
            cluster_score = min(location_analysis["max_density"] / 50.0, 1.0)
            fraud_scores.append(cluster_score * self.WEIGHT_LOCATION_CLUSTERING)

        # 3. High frequency (too many quests too fast)
        if frequency_analysis["max_per_hour"] >= self.MAX_QUESTS_PER_HOUR_THRESHOLD:
            fraud_flags["high_frequency_spike"] = frequency_analysis["max_per_hour"]
            freq_score = min(frequency_analysis["max_per_hour"] / 10.0, 1.0)
            fraud_scores.append(freq_score * self.WEIGHT_HIGH_FREQUENCY)

        # 4. High rejection rate
        if rejection_analysis["rejection_rate"] > 0.3:  # >30% rejected
            fraud_flags["high_rejection_rate"] = rejection_analysis["rejection_rate"]
            reject_score = rejection_analysis["rejection_rate"]
            fraud_scores.append(reject_score * self.WEIGHT_REJECTION_RATE)

        # Calculate composite risk score
        calculated_risk = sum(fraud_scores) if fraud_scores else 0.0
        calculated_risk = min(calculated_risk, 1.0)  # Cap at 1.0

        # Create behavior pattern record
        pattern = CollectorBehaviorPattern(
            collector_id=collector_id,
            analysis_window_start=window_start,
            analysis_window_end=window_end,
            unique_locations_count=location_analysis["unique_count"],
            location_cluster_radius_meters=location_analysis["cluster_radius"],
            max_location_density=location_analysis["max_density"],
            quests_completed_count=len(quests),
            average_completion_time_minutes=timing_analysis["avg_time"],
            min_completion_time_minutes=timing_analysis["min_time"],
            suspicious_rapid_completions=timing_analysis["suspicious_rapid_count"],
            quests_per_day_avg=frequency_analysis["per_day_avg"],
            max_quests_in_hour=frequency_analysis["max_per_hour"],
            fraud_flags=fraud_flags,
            calculated_risk_score=calculated_risk,
        )

        # Save to database
        session.add(pattern)

        # Update user's fraud_risk_score
        user = await session.get(User, collector_id)
        if user:
            user.fraud_risk_score = calculated_risk
            user.last_fraud_check = datetime.utcnow()

        return pattern

    async def _analyze_timing_patterns(
        self, quests: List[Quest], session: AsyncSession
    ) -> Dict:
        """Analyze quest completion timing patterns"""
        completion_times = []
        suspicious_count = 0

        for quest in quests:
            if quest.assigned_at and quest.completed_at:
                duration = (quest.completed_at - quest.assigned_at).total_seconds() / 60
                completion_times.append(duration)

                if duration < self.SUSPICIOUS_COMPLETION_TIME_MINUTES:
                    suspicious_count += 1

        return {
            "avg_time": (
                sum(completion_times) / len(completion_times) if completion_times else None
            ),
            "min_time": min(completion_times) if completion_times else None,
            "max_time": max(completion_times) if completion_times else None,
            "suspicious_rapid_count": suspicious_count,
        }

    async def _analyze_location_patterns(
        self, quests: List[Quest], session: AsyncSession
    ) -> Dict:
        """Analyze spatial clustering of quest locations"""
        # Extract locations
        locations = []
        for quest in quests:
            # Get lat/lng from PostGIS geometry
            query = select(
                ST_Y(Quest.location).label("lat"), ST_X(Quest.location).label("lng")
            ).where(Quest.id == quest.id)

            result = await session.execute(query)
            row = result.one()
            locations.append((row.lat, row.lng))

        # Count unique geohash locations (precision 7 ≈ 150m)
        geohashes = [geohash.encode(lat, lng, precision=7) for lat, lng in locations]
        unique_count = len(set(geohashes))

        # Calculate location density (quests per km²)
        if len(locations) > 1:
            # Simple bounding box area calculation
            lats = [loc[0] for loc in locations]
            lngs = [loc[1] for loc in locations]

            lat_range = max(lats) - min(lats)
            lng_range = max(lngs) - min(lngs)

            # Approximate area in km² (rough, assumes small area)
            area_km2 = (lat_range * 111) * (lng_range * 111)  # 1° ≈ 111km
            area_km2 = max(area_km2, 0.01)  # Avoid division by zero

            density = len(quests) / area_km2
        else:
            density = 0.0

        # Calculate cluster radius (average distance from centroid)
        if len(locations) > 1:
            center_lat = sum(lat for lat, _ in locations) / len(locations)
            center_lng = sum(lng for _, lng in locations) / len(locations)

            # Haversine distance calculation
            distances = []
            for lat, lng in locations:
                distance_m = self._haversine_distance(center_lat, center_lng, lat, lng)
                distances.append(distance_m)

            cluster_radius = sum(distances) / len(distances)
        else:
            cluster_radius = None

        return {
            "unique_count": unique_count,
            "cluster_radius": cluster_radius,
            "max_density": density,
        }

    def _haversine_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """
        Calculate the great circle distance between two points
        on the earth (specified in decimal degrees).
        Returns distance in meters.
        """
        # Convert decimal degrees to radians
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

        # Haversine formula
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        # Radius of earth in meters
        r = 6371000
        return r * c

    def _analyze_frequency_patterns(self, quests: List[Quest]) -> Dict:
        """Analyze quest completion frequency patterns"""
        if not quests:
            return {"per_day_avg": 0.0, "max_per_hour": 0}

        # Group by day
        days = {}
        for quest in quests:
            if quest.completed_at:
                day_key = quest.completed_at.date()
                days[day_key] = days.get(day_key, 0) + 1

        per_day_avg = sum(days.values()) / len(days) if days else 0.0

        # Group by hour to find spikes
        hours = {}
        for quest in quests:
            if quest.completed_at:
                hour_key = quest.completed_at.replace(minute=0, second=0, microsecond=0)
                hours[hour_key] = hours.get(hour_key, 0) + 1

        max_per_hour = max(hours.values()) if hours else 0

        return {"per_day_avg": per_day_avg, "max_per_hour": max_per_hour}

    def _analyze_rejection_rate(self, quests: List[Quest]) -> Dict:
        """Analyze quest rejection rate"""
        total = len(quests)
        rejected = sum(1 for q in quests if q.status == QuestStatus.REJECTED)

        return {
            "total": total,
            "rejected": rejected,
            "rejection_rate": rejected / total if total > 0 else 0.0,
        }

    def _create_neutral_pattern(
        self, collector_id: UUID, window_start: datetime, window_end: datetime
    ) -> CollectorBehaviorPattern:
        """Create neutral pattern for collectors with insufficient data"""
        return CollectorBehaviorPattern(
            collector_id=collector_id,
            analysis_window_start=window_start,
            analysis_window_end=window_end,
            unique_locations_count=0,
            quests_completed_count=0,
            calculated_risk_score=0.0,
            fraud_flags={"insufficient_data": True},
        )

    def get_dynamic_ai_threshold(self, fraud_risk_score: float) -> float:
        """
        Calculate dynamic AI confidence threshold based on fraud risk.

        Low-risk users: Lower threshold (easier to auto-approve)
        High-risk users: Higher threshold (stricter verification)
        """
        base_threshold = settings.AI_VERIFICATION_CONFIDENCE_THRESHOLD  # e.g., 0.70

        if fraud_risk_score < 0.2:
            # Low risk - reduce threshold by 10%
            return max(base_threshold - 0.10, 0.50)
        elif fraud_risk_score < 0.5:
            # Medium risk - use base threshold
            return base_threshold
        elif fraud_risk_score < 0.7:
            # High risk - increase threshold by 10%
            return min(base_threshold + 0.10, 0.90)
        else:
            # Very high risk - increase threshold by 15%
            return min(base_threshold + 0.15, 0.95)


# Singleton
_fraud_service: Optional[FraudDetectionService] = None


def get_fraud_detection_service() -> FraudDetectionService:
    """Get or create fraud detection service singleton"""
    global _fraud_service
    if _fraud_service is None:
        _fraud_service = FraudDetectionService()
    return _fraud_service
