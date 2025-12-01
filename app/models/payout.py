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
    from app.models.transaction import Transaction


class PayoutStatus(str, enum.Enum):
    """Payout status states"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PayoutMethod(str, enum.Enum):
    """Payout methods"""
    STRIPE_TRANSFER = "stripe_transfer"
    BANK_TRANSFER = "bank_transfer"
    WALLET = "wallet"


class Payout(Base):
    """Payout model for actual payment disbursements"""
    __tablename__ = "payouts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True
    )

    amount: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="USD")

    payout_method: Mapped[PayoutMethod] = mapped_column(SQLEnum(PayoutMethod), nullable=False)
    status: Mapped[PayoutStatus] = mapped_column(
        SQLEnum(PayoutStatus), default=PayoutStatus.PENDING, index=True
    )

    # Stripe payout ID if using Stripe
    stripe_transfer_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    stripe_account_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Bank details (for direct bank transfers)
    bank_account_last4: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User")
    transaction: Mapped[Optional["Transaction"]] = relationship("Transaction")

    def __repr__(self) -> str:
        return f"<Payout {self.id} - {self.amount} {self.currency} ({self.status})>"
