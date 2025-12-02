import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.quest import Quest
    from app.models.user import User


class QuestAssignmentHistory(Base):
    """Track assignment attempts for debugging and optimization"""
    __tablename__ = "quest_assignment_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    quest_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("quests.id"), nullable=False, index=True
    )

    assigned_collector_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    assignment_method: Mapped[str] = mapped_column(
        String(50), nullable=False
    )

    assignment_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )

    distance_km: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )

    collector_workload_at_assignment: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )

    was_successful: Mapped[bool] = mapped_column(
        Boolean, default=True
    )

    failure_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    # Relationships
    quest: Mapped["Quest"] = relationship("Quest", back_populates="assignment_history")
    assigned_collector: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[assigned_collector_id]
    )

    def __repr__(self) -> str:
        return f"<QuestAssignmentHistory {self.quest_id} - {self.assignment_method}>"
