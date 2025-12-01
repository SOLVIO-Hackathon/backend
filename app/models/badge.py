import uuid
import enum
from datetime import datetime
from typing import TYPE_CHECKING
from sqlalchemy import Enum as SQLEnum, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class BadgeType(str, enum.Enum):
    """Badge types for gamification"""
    E_WASTE_PRO = "e_waste_pro"
    ORGANIC_HERO = "organic_hero"
    TOP_COLLECTOR = "top_collector"
    TRUSTED_KABADIWALA = "trusted_kabadiwala"
    RECYCLING_CHAMPION = "recycling_champion"
    VERIFIED_SELLER = "verified_seller"


class Badge(Base):
    """Badge model for user achievements"""
    __tablename__ = "badges"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    badge_type: Mapped[BadgeType] = mapped_column(SQLEnum(BadgeType), nullable=False)

    awarded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="badges")

    def __repr__(self) -> str:
        return f"<Badge {self.badge_type} for User {self.user_id}>"
