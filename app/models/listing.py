import uuid
import enum
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from decimal import Decimal
from sqlalchemy import String, Enum as SQLEnum, DateTime, Text, JSON, ForeignKey, DECIMAL, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.bid import Bid


class DeviceType(str, enum.Enum):
    """E-waste device types"""
    MOBILE = "mobile"
    LAPTOP = "laptop"
    DESKTOP = "desktop"
    MONITOR = "monitor"
    TABLET = "tablet"
    OTHER = "other"


class DeviceCondition(str, enum.Enum):
    """Device condition"""
    WORKING = "working"
    PARTIALLY_WORKING = "partially_working"
    NOT_WORKING = "not_working"


class ListingStatus(str, enum.Enum):
    """Listing status states"""
    LISTED = "listed"
    BIDDING = "bidding"
    ACCEPTED = "accepted"
    PICKED_UP = "picked_up"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Listing(Base):
    """E-waste marketplace listing model"""
    __tablename__ = "listings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    seller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    buyer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    device_type: Mapped[DeviceType] = mapped_column(SQLEnum(DeviceType), nullable=False)
    device_name: Mapped[str] = mapped_column(String(255), nullable=False)
    condition: Mapped[DeviceCondition] = mapped_column(SQLEnum(DeviceCondition), nullable=False)

    image_urls: Mapped[list] = mapped_column(JSON, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Pricing
    estimated_value_min: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    estimated_value_max: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    base_price: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2), nullable=True)
    final_price: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(10, 2), nullable=True)

    # Location
    location: Mapped[str] = mapped_column(Geometry("POINT", srid=4326), nullable=False)

    status: Mapped[ListingStatus] = mapped_column(
        SQLEnum(ListingStatus), default=ListingStatus.LISTED, index=True
    )

    # AI Classification
    ai_classification: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Weight verification
    weight_kg: Mapped[Optional[Decimal]] = mapped_column(DECIMAL(5, 2), nullable=True)
    weight_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    pickup_scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    seller: Mapped["User"] = relationship(
        "User", back_populates="listings_as_seller", foreign_keys=[seller_id]
    )
    buyer: Mapped[Optional["User"]] = relationship(
        "User", back_populates="listings_as_buyer", foreign_keys=[buyer_id]
    )
    bids: Mapped[List["Bid"]] = relationship("Bid", back_populates="listing")

    def __repr__(self) -> str:
        return f"<Listing {self.id} - {self.device_name} ({self.status})>"
