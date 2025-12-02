import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import String, Integer, Float, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class CollectorBehaviorPattern(Base):
    """Track collector behavior patterns for fraud detection"""
    __tablename__ = "collector_behavior_patterns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    collector_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    # Time-based patterns
    analysis_window_start: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True
    )
    analysis_window_end: Mapped[datetime] = mapped_column(
        DateTime, nullable=False
    )

    # Location clustering metrics
    unique_locations_count: Mapped[int] = mapped_column(
        Integer, default=0
    )

    location_cluster_radius_meters: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    max_location_density: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    # Timing patterns
    quests_completed_count: Mapped[int] = mapped_column(
        Integer, default=0
    )

    average_completion_time_minutes: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    min_completion_time_minutes: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    suspicious_rapid_completions: Mapped[int] = mapped_column(
        Integer, default=0
    )

    # Frequency patterns
    quests_per_day_avg: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    max_quests_in_hour: Mapped[int] = mapped_column(
        Integer, default=0
    )

    # Fraud indicators
    fraud_flags: Mapped[dict] = mapped_column(
        JSON, default=dict
    )

    calculated_risk_score: Mapped[float] = mapped_column(
        Float, default=0.0
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )

    # Relationship
    collector: Mapped["User"] = relationship("User", back_populates="behavior_patterns")

    def __repr__(self) -> str:
        return f"<CollectorBehaviorPattern {self.collector_id} - Risk: {self.calculated_risk_score:.2f}>"
