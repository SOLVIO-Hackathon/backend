"""
Automatic collector assignment service using PostGIS spatial queries
and workload balancing algorithms.
"""

from typing import Optional, List, Tuple, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_SetSRID, ST_Point, ST_Distance, ST_X, ST_Y

from app.models.user import User, UserType
from app.models.quest import Quest, QuestStatus
from app.models.assignment_history import QuestAssignmentHistory
from app.core.config import settings


class CollectorAssignmentService:
    """Service for automatic collector assignment"""

    # Configuration constants
    MAX_SEARCH_RADIUS_KM = 10.0  # Start with 10km radius
    EXPAND_RADIUS_STEP_KM = 5.0  # Expand by 5km if no collectors found
    MAX_RADIUS_KM = 50.0  # Don't search beyond 50km
    STALE_LOCATION_MINUTES = 60  # Consider location stale after 1 hour

    async def assign_collector_to_quest(
        self, quest: Quest, session: AsyncSession
    ) -> Tuple[Optional[User], str]:
        """
        Automatically assign the best available collector to a quest.

        Returns:
            Tuple of (assigned_collector, reason_message)
        """
        # Extract quest location
        quest_lat = await self._extract_latitude(quest.location, session)
        quest_lng = await self._extract_longitude(quest.location, session)

        # Try increasing radii until we find collectors
        current_radius = self.MAX_SEARCH_RADIUS_KM

        while current_radius <= self.MAX_RADIUS_KM:
            collectors = await self._find_nearby_collectors(
                quest_lat, quest_lng, current_radius, session
            )

            if collectors:
                # Found collectors - now select the best one
                best_collector = await self._select_best_collector(
                    collectors, quest_lat, quest_lng, session
                )

                if best_collector:
                    # Assign the quest
                    await self._assign_quest(
                        quest,
                        best_collector,
                        session,
                        distance_km=best_collector["distance_km"],
                    )

                    return (
                        best_collector["user"],
                        f"Assigned to collector {best_collector['distance_km']:.1f}km away",
                    )

            # Expand search radius
            current_radius += self.EXPAND_RADIUS_STEP_KM

        # No collectors found within maximum radius
        await self._log_assignment_failure(
            quest, "No available collectors within 50km", session
        )
        return None, "No collectors available in your area"

    async def _find_nearby_collectors(
        self, latitude: float, longitude: float, radius_km: float, session: AsyncSession
    ) -> List[Dict[str, Any]]:
        """
        Find available collectors within radius using PostGIS.

        Returns list of collectors with their current workload and distance.
        """
        radius_meters = radius_km * 1000
        quest_point = ST_SetSRID(ST_Point(longitude, latitude), 4326)

        # Subquery: count active quests per collector
        active_quests_subquery = (
            select(Quest.collector_id, func.count(Quest.id).label("active_count"))
            .where(Quest.status.in_([QuestStatus.ASSIGNED, QuestStatus.IN_PROGRESS]))
            .group_by(Quest.collector_id)
            .subquery()
        )

        # Main query: find collectors with location, distance, and workload
        query = (
            select(
                User,
                ST_Distance(
                    ST_SetSRID(
                        ST_Point(User.current_location_lng, User.current_location_lat),
                        4326,
                    ),
                    quest_point,
                ).label("distance_meters"),
                func.coalesce(active_quests_subquery.c.active_count, 0).label(
                    "active_quests"
                ),
            )
            .outerjoin(
                active_quests_subquery,
                User.id == active_quests_subquery.c.collector_id,
            )
            .where(
                and_(
                    User.user_type == UserType.COLLECTOR,
                    User.is_active == True,
                    User.collector_status == "available",
                    User.current_location_lat.isnot(None),
                    User.current_location_lng.isnot(None),
                    # Location must be recent (not stale)
                    User.last_location_update
                    >= datetime.utcnow() - timedelta(minutes=self.STALE_LOCATION_MINUTES),
                    # Within radius
                    ST_Distance(
                        ST_SetSRID(
                            ST_Point(
                                User.current_location_lng, User.current_location_lat
                            ),
                            4326,
                        ),
                        quest_point,
                    )
                    <= radius_meters,
                    # Not overloaded
                    func.coalesce(active_quests_subquery.c.active_count, 0)
                    < User.max_concurrent_quests,
                )
            )
            .order_by("distance_meters")
        )

        result = await session.execute(query)
        rows = result.all()

        return [
            {
                "user": row[0],
                "distance_km": row[1] / 1000.0,
                "active_quests": row[2],
            }
            for row in rows
        ]

    async def _select_best_collector(
        self,
        collectors: List[Dict[str, Any]],
        quest_lat: float,
        quest_lng: float,
        session: AsyncSession,
    ) -> Optional[Dict[str, Any]]:
        """
        Select the best collector using weighted scoring.

        Scoring factors:
        1. Distance (40% weight) - closer is better
        2. Workload (40% weight) - fewer active quests is better
        3. Reputation (20% weight) - higher reputation is better
        """
        if not collectors:
            return None

        # Calculate scores
        max_distance = max(c["distance_km"] for c in collectors)
        max_active = max(c["active_quests"] for c in collectors)
        max_reputation = max(c["user"].reputation_score for c in collectors) or 1.0

        scored_collectors = []

        for collector in collectors:
            # Normalize scores (0-1, where 1 is best)
            distance_score = (
                1.0 - (collector["distance_km"] / max_distance if max_distance > 0 else 0)
            )
            workload_score = (
                1.0 - (collector["active_quests"] / max_active if max_active > 0 else 0)
            )
            reputation_score = (
                collector["user"].reputation_score / max_reputation
                if max_reputation > 0
                else 0.5
            )

            # Weighted composite score
            composite_score = (
                distance_score * 0.40 + workload_score * 0.40 + reputation_score * 0.20
            )

            scored_collectors.append({**collector, "score": composite_score})

        # Return collector with highest score
        best = max(scored_collectors, key=lambda x: x["score"])
        return best

    async def _assign_quest(
        self,
        quest: Quest,
        collector_info: Dict[str, Any],
        session: AsyncSession,
        distance_km: float,
    ):
        """Assign quest to collector and log the assignment"""
        collector = collector_info["user"]

        quest.collector_id = collector.id
        quest.status = QuestStatus.ASSIGNED
        quest.assigned_at = datetime.utcnow()

        # Log assignment history
        history = QuestAssignmentHistory(
            quest_id=quest.id,
            assigned_collector_id=collector.id,
            assignment_method="automatic",
            assignment_reason=f"Best match: {collector_info['score']:.2f} score",
            distance_km=distance_km,
            collector_workload_at_assignment=collector_info["active_quests"],
            was_successful=True,
        )
        session.add(history)

    async def _log_assignment_failure(
        self, quest: Quest, reason: str, session: AsyncSession
    ):
        """Log failed assignment attempt"""
        history = QuestAssignmentHistory(
            quest_id=quest.id,
            assigned_collector_id=None,
            assignment_method="automatic",
            assignment_reason="Assignment failed",
            failure_reason=reason,
            was_successful=False,
        )
        session.add(history)

    async def _extract_latitude(
        self, location, session: AsyncSession
    ) -> float:
        """Extract latitude from PostGIS geometry"""
        query = select(ST_Y(location))
        result = await session.execute(query)
        return result.scalar()

    async def _extract_longitude(
        self, location, session: AsyncSession
    ) -> float:
        """Extract longitude from PostGIS geometry"""
        query = select(ST_X(location))
        result = await session.execute(query)
        return result.scalar()


# Singleton instance
_assignment_service: Optional[CollectorAssignmentService] = None


def get_assignment_service() -> CollectorAssignmentService:
    """Get or create assignment service singleton"""
    global _assignment_service
    if _assignment_service is None:
        _assignment_service = CollectorAssignmentService()
    return _assignment_service
