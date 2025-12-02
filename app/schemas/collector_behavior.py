"""Pydantic schemas for collector behavior analysis"""

from typing import Dict, Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel


class CollectorBehaviorResponse(BaseModel):
    """Schema for behavior pattern response"""

    id: UUID
    collector_id: UUID
    analysis_window_start: datetime
    analysis_window_end: datetime
    unique_locations_count: int
    location_cluster_radius_meters: Optional[float]
    max_location_density: Optional[float]
    quests_completed_count: int
    average_completion_time_minutes: Optional[float]
    min_completion_time_minutes: Optional[float]
    suspicious_rapid_completions: int
    quests_per_day_avg: Optional[float]
    max_quests_in_hour: int
    fraud_flags: Dict
    calculated_risk_score: float
    created_at: datetime

    model_config = {"from_attributes": True}


class UpdateLocationRequest(BaseModel):
    """Request to update collector location"""

    latitude: float
    longitude: float


class UpdateAvailabilityRequest(BaseModel):
    """Request to update collector availability"""

    status: str  # "available", "busy", "offline"
