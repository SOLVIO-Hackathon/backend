from typing import Optional
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from pydantic import BaseModel, Field

from app.models.bid import BidStatus
from app.schemas.user import UserPublic


class BidBase(BaseModel):
    """Base bid schema"""
    offered_price: Decimal = Field(..., gt=0, description="Offered price in BDT")
    pickup_time_estimate: str = Field(..., max_length=100, description="Estimated pickup time")
    message: Optional[str] = Field(None, max_length=500)


class BidCreate(BidBase):
    """Schema for creating a bid"""
    listing_id: UUID

    model_config = {
        "json_schema_extra": {
            "example": {
                "listing_id": "123e4567-e89b-12d3-a456-426614174000",
                "offered_price": 2400.00,
                "pickup_time_estimate": "2 hours",
                "message": "I can pick up this evening. Free transportation."
            }
        }
    }


class BidUpdate(BaseModel):
    """Schema for updating a bid"""
    status: BidStatus


class BidResponse(BaseModel):
    """Schema for bid response"""
    id: UUID
    listing_id: UUID
    kabadiwala_id: UUID
    offered_price: Decimal
    pickup_time_estimate: str
    message: Optional[str]
    status: BidStatus
    created_at: datetime
    updated_at: datetime
    kabadiwala: Optional[UserPublic] = None

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "listing_id": "456e4567-e89b-12d3-a456-426614174000",
                "kabadiwala_id": "789e4567-e89b-12d3-a456-426614174000",
                "offered_price": 2400.00,
                "pickup_time_estimate": "2 hours",
                "status": "pending"
            }
        }
    }
