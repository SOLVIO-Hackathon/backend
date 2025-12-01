from typing import Optional, List
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from pydantic import BaseModel, Field

from app.models.listing import DeviceType, DeviceCondition, ListingStatus
from app.schemas.common import LocationSchema
from app.schemas.user import UserPublic


class ListingBase(BaseModel):
    """Base listing schema"""
    device_type: DeviceType
    device_name: str = Field(..., min_length=1, max_length=255)
    condition: DeviceCondition
    description: Optional[str] = None
    location: LocationSchema


class ListingCreate(ListingBase):
    """Schema for creating a listing"""
    image_urls: List[str] = Field(..., min_items=1, max_items=5)

    model_config = {
        "json_schema_extra": {
            "example": {
                "device_type": "laptop",
                "device_name": "Dell Latitude E7450",
                "condition": "working",
                "description": "Good condition laptop, minor scratches on body",
                "location": {"latitude": 23.7808, "longitude": 90.4219},
                "image_urls": [
                    "https://storage.example.com/devices/laptop1.jpg",
                    "https://storage.example.com/devices/laptop2.jpg"
                ]
            }
        }
    }


class ListingUpdate(BaseModel):
    """Schema for updating a listing"""
    status: Optional[ListingStatus] = None
    buyer_id: Optional[UUID] = None
    final_price: Optional[Decimal] = None
    weight_kg: Optional[Decimal] = None
    weight_verified: Optional[bool] = None
    pickup_scheduled_at: Optional[datetime] = None


class ListingResponse(BaseModel):
    """Schema for listing response"""
    id: UUID
    seller_id: UUID
    buyer_id: Optional[UUID]
    device_type: DeviceType
    device_name: str
    condition: DeviceCondition
    image_urls: List[str]
    description: Optional[str]
    estimated_value_min: Decimal
    estimated_value_max: Decimal
    final_price: Optional[Decimal]
    location: dict  # GeoJSON representation
    status: ListingStatus
    ai_classification: Optional[dict]
    weight_kg: Optional[Decimal]
    weight_verified: bool
    pickup_scheduled_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    seller: Optional[UserPublic] = None
    buyer: Optional[UserPublic] = None

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "seller_id": "456e4567-e89b-12d3-a456-426614174000",
                "device_type": "laptop",
                "device_name": "Dell Latitude E7450",
                "condition": "working",
                "estimated_value_min": 2200.00,
                "estimated_value_max": 2600.00,
                "status": "listed"
            }
        }
    }


class ListingList(BaseModel):
    """Schema for paginated listing list"""
    items: List[ListingResponse]
    total: int
    skip: int
    limit: int
