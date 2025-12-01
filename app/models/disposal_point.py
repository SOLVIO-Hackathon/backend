import uuid
import enum
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Float, Enum as SQLEnum, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry

from app.core.database import Base


class DisposalPointType(str, enum.Enum):
    """Types of disposal points"""
    RECYCLING_CENTER = "recycling_center"
    LANDFILL = "landfill"
    E_WASTE_CENTER = "e_waste_center"
    ORGANIC_COMPOSTING = "organic_composting"
    HAZARDOUS_WASTE = "hazardous_waste"


class DisposalPoint(Base):
    """Disposal point model for waste routing"""
    __tablename__ = "disposal_points"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    address: Mapped[str] = mapped_column(String(500), nullable=False)

    point_type: Mapped[DisposalPointType] = mapped_column(
        SQLEnum(DisposalPointType), nullable=False, index=True
    )

    # Geospatial data
    location: Mapped[str] = mapped_column(
        Geometry("POINT", srid=4326), nullable=False
    )

    # Operating hours (simplified as string for hackathon)
    operating_hours: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Accepted waste types (comma-separated for simplicity)
    accepted_waste_types: Mapped[str] = mapped_column(String(255), nullable=False)

    is_active: Mapped[bool] = mapped_column(default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<DisposalPoint {self.name} ({self.point_type})>"
