"""Rating model for kabadiwala reviews"""

import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.listing import Listing


class Rating(Base):
    """Rating/Review model for kabadiwala performance"""
    __tablename__ = "ratings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Seller rates the kabadiwala
    seller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    kabadiwala_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("listings.id"), nullable=False, index=True
    )

    # Rating 1-5 stars
    rating: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    # Optional review text
    review: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Specific criteria ratings (optional, 1-5 each)
    punctuality_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    professionalism_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    communication_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    seller: Mapped["User"] = relationship(
        "User", foreign_keys=[seller_id], backref="ratings_given"
    )
    kabadiwala: Mapped["User"] = relationship(
        "User", foreign_keys=[kabadiwala_id], backref="ratings_received"
    )
    listing: Mapped["Listing"] = relationship("Listing", backref="rating")

    # Constraints
    __table_args__ = (
        CheckConstraint('rating >= 1 AND rating <= 5', name='rating_range'),
        CheckConstraint('punctuality_rating IS NULL OR (punctuality_rating >= 1 AND punctuality_rating <= 5)', name='punctuality_range'),
        CheckConstraint('professionalism_rating IS NULL OR (professionalism_rating >= 1 AND professionalism_rating <= 5)', name='professionalism_range'),
        CheckConstraint('communication_rating IS NULL OR (communication_rating >= 1 AND communication_rating <= 5)', name='communication_range'),
    )

    def __repr__(self) -> str:
        return f"<Rating {self.id} - {self.rating} stars for Kabadiwala {self.kabadiwala_id}>"
