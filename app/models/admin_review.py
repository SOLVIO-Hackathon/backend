import uuid
import enum
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Float, Enum as SQLEnum, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.quest import Quest


class ReviewStatus(str, enum.Enum):
    """Admin review status states"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class FlagReason(str, enum.Enum):
    """Reason for flagging an item for review"""
    LOW_AI_CONFIDENCE = "low_ai_confidence"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    USER_REPORT = "user_report"
    FRAUD_DETECTION = "fraud_detection"
    LOCATION_MISMATCH = "location_mismatch"


class AdminReview(Base):
    """Admin review model for human-in-the-loop verification"""
    __tablename__ = "admin_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    quest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quests.id"), nullable=False, index=True
    )
    reviewer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    flag_reason: Mapped[FlagReason] = mapped_column(SQLEnum(FlagReason), nullable=False)
    ai_confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    status: Mapped[ReviewStatus] = mapped_column(
        SQLEnum(ReviewStatus), default=ReviewStatus.PENDING, index=True
    )

    ai_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    admin_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    quest: Mapped["Quest"] = relationship("Quest", backref="admin_reviews")
    reviewer: Mapped[Optional["User"]] = relationship("User")

    def __repr__(self) -> str:
        return f"<AdminReview {self.id} - Quest {self.quest_id} ({self.status})>"
