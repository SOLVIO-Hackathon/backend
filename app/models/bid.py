import uuid
import enum
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from decimal import Decimal
from sqlalchemy import String, Enum as SQLEnum, DateTime, Text, ForeignKey, DECIMAL
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.listing import Listing


class BidStatus(str, enum.Enum):
    """Bid status states"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class Bid(Base):
    """Bid model for e-waste marketplace"""
    __tablename__ = "bids"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("listings.id"), nullable=False, index=True
    )
    kabadiwala_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    offered_price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    pickup_time_estimate: Mapped[str] = mapped_column(String(100), nullable=False)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[BidStatus] = mapped_column(
        SQLEnum(BidStatus), default=BidStatus.PENDING, index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    listing: Mapped["Listing"] = relationship("Listing", back_populates="bids")
    kabadiwala: Mapped["User"] = relationship("User", back_populates="bids")

    def __repr__(self) -> str:
        return f"<Bid {self.id} - {self.offered_price} BDT ({self.status})>"
