import uuid
import enum
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, Text, Enum as SQLEnum, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.quest import Quest


class NotificationType(str, enum.Enum):
    """Notification types"""
    QUEST_CREATED = "quest_created"
    QUEST_ASSIGNED = "quest_assigned"
    QUEST_COMPLETED = "quest_completed"
    QUEST_VERIFIED = "quest_verified"
    QUEST_REJECTED = "quest_rejected"
    PAYMENT_RECEIVED = "payment_received"
    FRAUD_ALERT = "fraud_alert"


class NotificationChannel(str, enum.Enum):
    """Notification delivery channels"""
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"


class Notification(Base):
    """Notification queue for user alerts"""
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    notification_type: Mapped[NotificationType] = mapped_column(
        SQLEnum(NotificationType), nullable=False
    )

    channel: Mapped[NotificationChannel] = mapped_column(
        SQLEnum(NotificationChannel), nullable=False
    )

    title: Mapped[str] = mapped_column(
        String(255), nullable=False
    )

    message: Mapped[str] = mapped_column(
        Text, nullable=False
    )

    related_quest_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quests.id"), nullable=True
    )

    extra_data: Mapped[dict] = mapped_column(
        JSON, default=dict
    )

    is_read: Mapped[bool] = mapped_column(
        Boolean, default=False
    )

    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="notifications")
    related_quest: Mapped[Optional["Quest"]] = relationship("Quest")

    def __repr__(self) -> str:
        return f"<Notification {self.notification_type} for {self.user_id}>"
