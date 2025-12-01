from typing import Optional, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.disposal_point import DisposalPointType
from app.schemas.common import LocationSchema


class DisposalPointCreate(BaseModel):
    """Schema for creating a disposal point"""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    address: str = Field(..., min_length=1, max_length=500)
    point_type: DisposalPointType
    location: LocationSchema
    operating_hours: Optional[str] = None
    contact_phone: Optional[str] = None
    accepted_waste_types: str = Field(..., description="Comma-separated waste types")

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "Dhaka Recycling Center",
                "description": "Municipal recycling facility",
                "address": "123 Green Road, Dhaka",
                "point_type": "recycling_center",
                "location": {"latitude": 23.8103, "longitude": 90.4125},
                "operating_hours": "Mon-Sat 8AM-6PM",
                "contact_phone": "+8801234567890",
                "accepted_waste_types": "recyclable,general"
            }
        }
    }


class DisposalPointResponse(BaseModel):
    """Schema for disposal point response"""
    id: UUID
    name: str
    description: Optional[str]
    address: str
    point_type: DisposalPointType
    location: dict  # GeoJSON
    operating_hours: Optional[str]
    contact_phone: Optional[str]
    accepted_waste_types: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class DisposalPointList(BaseModel):
    """Schema for disposal point list"""
    items: List[DisposalPointResponse]
    total: int


class RouteStep(BaseModel):
    """Schema for a route step"""
    instruction: str
    distance_meters: float
    duration_seconds: float
    maneuver: Optional[str] = None


class RouteResponse(BaseModel):
    """Schema for routing response"""
    origin: LocationSchema
    destination: DisposalPointResponse
    distance_km: float
    duration_minutes: float
    route_geometry: str  # Encoded polyline
    steps: List[RouteStep]


class NearestDisposalResponse(BaseModel):
    """Schema for nearest disposal point with routing"""
    disposal_point: DisposalPointResponse
    distance_km: float
    duration_minutes: float
    route_geometry: Optional[str] = None
