import uuid
import enum
from datetime import datetime
from typing import List
from sqlalchemy import String, Boolean, Float, Integer, Enum as SQLEnum, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class UserType(str, enum.Enum):
    """User role types"""
    CITIZEN = "citizen"
    COLLECTOR = "collector"
    KABADIWALA = "kabadiwala"
    ADMIN = "admin"


class User(Base):
    """User model for all user types"""
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=True)

    user_type: Mapped[UserType] = mapped_column(
        SQLEnum(UserType), default=UserType.CITIZEN, nullable=False
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    is_sponsor: Mapped[bool] = mapped_column(Boolean, default=False)

    reputation_score: Mapped[float] = mapped_column(Float, default=0.0)
    total_transactions: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    reported_quests: Mapped[List["Quest"]] = relationship(
        "Quest", back_populates="reporter", foreign_keys="Quest.reporter_id"
    )
    collected_quests: Mapped[List["Quest"]] = relationship(
        "Quest", back_populates="collector", foreign_keys="Quest.collector_id"
    )
    listings_as_seller: Mapped[List["Listing"]] = relationship(
        "Listing", back_populates="seller", foreign_keys="Listing.seller_id"
    )
    listings_as_buyer: Mapped[List["Listing"]] = relationship(
        "Listing", back_populates="buyer", foreign_keys="Listing.buyer_id"
    )
    bids: Mapped[List["Bid"]] = relationship("Bid", back_populates="kabadiwala")
    transactions: Mapped[List["Transaction"]] = relationship("Transaction", back_populates="user")
    badges: Mapped[List["Badge"]] = relationship("Badge", back_populates="user")

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.user_type})>"
