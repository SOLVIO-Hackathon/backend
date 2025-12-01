from typing import Optional, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.admin_review import ReviewStatus, FlagReason


class AdminReviewCreate(BaseModel):
    """Schema for creating an admin review (usually done automatically by AI)"""
    quest_id: UUID
    flag_reason: FlagReason
    ai_confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    ai_notes: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "quest_id": "123e4567-e89b-12d3-a456-426614174000",
                "flag_reason": "low_ai_confidence",
                "ai_confidence_score": 0.45,
                "ai_notes": "Location mismatch detected between before and after photos"
            }
        }
    }


class AdminReviewUpdate(BaseModel):
    """Schema for admin review decision"""
    status: ReviewStatus = Field(..., description="Decision: approved or rejected")
    admin_notes: Optional[str] = Field(None, description="Notes from the reviewer")

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "approved",
                "admin_notes": "Verified manually - cleanup confirmed via timestamp check"
            }
        }
    }


class AdminReviewResponse(BaseModel):
    """Schema for admin review response"""
    id: UUID
    quest_id: UUID
    reviewer_id: Optional[UUID]
    flag_reason: FlagReason
    ai_confidence_score: Optional[float]
    status: ReviewStatus
    ai_notes: Optional[str]
    admin_notes: Optional[str]
    created_at: datetime
    reviewed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class AdminReviewList(BaseModel):
    """Schema for paginated admin review list"""
    items: List[AdminReviewResponse]
    total: int
    pending_count: int
