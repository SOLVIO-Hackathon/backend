import uuid
import enum
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, Float, Enum as SQLEnum, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class WasteType(str, enum.Enum):
    """Types of waste"""
    ORGANIC = "organic"
    RECYCLABLE = "recyclable"
    GENERAL = "general"
    E_WASTE = "e_waste"


class Severity(str, enum.Enum):
    """Severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class QuestStatus(str, enum.Enum):
    """Quest status states"""
    REPORTED = "reported"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"
    REJECTED = "rejected"


class Quest(Base):
    """CleanQuest mission model"""
    __tablename__ = "quests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    reporter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    collector_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # Geospatial data
    location: Mapped[str] = mapped_column(
        Geometry("POINT", srid=4326), nullable=False
    )
    geohash: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    ward_geohash: Mapped[str] = mapped_column(String(5), index=True, nullable=False)  # First 5 chars for ward-level grouping

    waste_type: Mapped[WasteType] = mapped_column(SQLEnum(WasteType), nullable=False)
    severity: Mapped[Severity] = mapped_column(SQLEnum(Severity), default=Severity.MEDIUM)
    status: Mapped[QuestStatus] = mapped_column(
        SQLEnum(QuestStatus), default=QuestStatus.REPORTED, index=True
    )

    bounty_points: Mapped[int] = mapped_column(Integer, nullable=False)

    # Images
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    before_photo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    after_photo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # EXIF metadata
    before_photo_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    after_photo_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # AI verification
    ai_verification_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    verification_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamps
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    reporter: Mapped["User"] = relationship(
        "User", back_populates="reported_quests", foreign_keys=[reporter_id]
    )
    collector: Mapped[Optional["User"]] = relationship(
        "User", back_populates="collected_quests", foreign_keys=[collector_id]
    )

    def __repr__(self) -> str:
        return f"<Quest {self.id} - {self.waste_type} ({self.status})>"
