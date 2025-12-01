from typing import Optional, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.quest import WasteType, Severity, QuestStatus
from app.schemas.common import LocationSchema
from app.schemas.user import UserPublic


class QuestBase(BaseModel):
    """Base quest schema"""
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    location: LocationSchema
    waste_type: WasteType
    severity: Severity = Severity.MEDIUM


class QuestCreate(QuestBase):
    """Schema for creating a quest"""
    image_url: str = Field(..., description="URL of the waste photo")

    model_config = {
        "json_schema_extra": {
            "example": {
                "title": "Plastic waste pile near Dhanmondi Lake",
                "description": "Large amount of plastic bottles and bags",
                "location": {"latitude": 23.7461, "longitude": 90.3742},
                "waste_type": "recyclable",
                "severity": "high",
                "image_url": "https://storage.example.com/waste-photos/abc123.jpg"
            }
        }
    }


class QuestUpdate(BaseModel):
    """Schema for updating a quest"""
    collector_id: Optional[UUID] = None
    status: Optional[QuestStatus] = None
    before_photo_url: Optional[str] = None
    after_photo_url: Optional[str] = None
    before_photo_metadata: Optional[dict] = None
    after_photo_metadata: Optional[dict] = None
    ai_verification_score: Optional[float] = None
    verification_notes: Optional[str] = None


class QuestResponse(BaseModel):
    """Schema for quest response"""
    id: UUID
    reporter_id: UUID
    collector_id: Optional[UUID]
    title: str
    description: Optional[str]
    location: dict  # GeoJSON representation
    geohash: str
    waste_type: WasteType
    severity: Severity
    status: QuestStatus
    bounty_points: int
    image_url: str
    before_photo_url: Optional[str]
    after_photo_url: Optional[str]
    ai_verification_score: Optional[float]
    verification_notes: Optional[str]
    assigned_at: Optional[datetime]
    completed_at: Optional[datetime]
    verified_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    reporter: Optional[UserPublic] = None
    collector: Optional[UserPublic] = None

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "reporter_id": "456e4567-e89b-12d3-a456-426614174000",
                "collector_id": "789e4567-e89b-12d3-a456-426614174000",
                "title": "Plastic waste pile near Dhanmondi Lake",
                "waste_type": "recyclable",
                "severity": "high",
                "status": "completed",
                "bounty_points": 50
            }
        }
    }


class QuestList(BaseModel):
    """Schema for paginated quest list"""
    items: List[QuestResponse]
    total: int
    skip: int
    limit: int


class QuestVerificationRequest(BaseModel):
    """Schema for verifying a quest"""
    status: QuestStatus = Field(..., description="Verification status (verified or rejected)")
    verification_notes: Optional[str] = Field(None, description="Admin notes about verification")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "verified",
                "verification_notes": "Photos verified, cleanup completed successfully"
            }
        }
    }
