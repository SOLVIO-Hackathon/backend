from typing import List, Dict
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.quest import WasteType, Severity, QuestStatus
from app.schemas.user import UserPublic


class HeatmapPoint(BaseModel):
    """Heatmap data point"""
    id: str
    latitude: float
    longitude: float
    waste_type: WasteType
    severity: Severity
    status: QuestStatus
    created_at: datetime

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "latitude": 23.7808,
                "longitude": 90.4219,
                "waste_type": "recyclable",
                "severity": "high",
                "status": "completed",
                "created_at": "2024-12-01T10:30:00"
            }
        }
    }


class LeaderboardEntry(BaseModel):
    """Leaderboard entry"""
    rank: int
    user: UserPublic
    quests_completed: int
    total_bounty_earned: float
    badges_count: int

    model_config = {
        "json_schema_extra": {
            "example": {
                "rank": 1,
                "user": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "full_name": "Top Collector",
                    "user_type": "collector",
                    "reputation_score": 4.9
                },
                "quests_completed": 42,
                "total_bounty_earned": 2100.0,
                "badges_count": 5
            }
        }
    }


class WardStats(BaseModel):
    """Ward-level statistics"""
    ward_name: str
    total_quests: int
    completed_quests: int
    pending_quests: int
    total_waste_kg: float

    model_config = {
        "json_schema_extra": {
            "example": {
                "ward_name": "Ward 25 - Dhanmondi",
                "total_quests": 150,
                "completed_quests": 120,
                "pending_quests": 30,
                "total_waste_kg": 450.5
            }
        }
    }


class AnalyticsOverview(BaseModel):
    """Overall platform analytics"""
    total_users: int
    total_collectors: int
    total_kabadiwalas: int
    total_quests: int
    quests_completed: int
    quests_pending: int
    total_listings: int
    listings_active: int
    total_transactions_value: float
    total_waste_collected_kg: float

    model_config = {
        "json_schema_extra": {
            "example": {
                "total_users": 1250,
                "total_collectors": 180,
                "total_kabadiwalas": 45,
                "total_quests": 890,
                "quests_completed": 650,
                "quests_pending": 240,
                "total_listings": 320,
                "listings_active": 85,
                "total_transactions_value": 125000.0,
                "total_waste_collected_kg": 2450.5
            }
        }
    }


class TimeSeriesData(BaseModel):
    """Time series data for charts"""
    date: datetime
    value: float
    label: str


class DashboardResponse(BaseModel):
    """Complete dashboard data"""
    analytics: AnalyticsOverview
    heatmap: List[HeatmapPoint]
    leaderboard: List[LeaderboardEntry]
    ward_stats: List[WardStats]
    quest_trend: List[TimeSeriesData]

    model_config = {
        "json_schema_extra": {
            "example": {
                "analytics": {
                    "total_users": 1250,
                    "total_quests": 890,
                    "quests_completed": 650
                },
                "heatmap": [],
                "leaderboard": [],
                "ward_stats": [],
                "quest_trend": []
            }
        }
    }
