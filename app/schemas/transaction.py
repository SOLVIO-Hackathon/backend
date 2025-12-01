from typing import Optional, List
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from pydantic import BaseModel, Field

from app.models.transaction import TransactionType, PaymentMethod, PaymentStatus


class TransactionBase(BaseModel):
    """Base transaction schema"""
    transaction_type: TransactionType
    amount: Decimal = Field(..., gt=0)
    payment_method: PaymentMethod
    notes: Optional[str] = None


class TransactionCreate(TransactionBase):
    """Schema for creating a transaction"""
    user_id: UUID
    quest_id: Optional[UUID] = None
    listing_id: Optional[UUID] = None
    commission_amount: Optional[Decimal] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "transaction_type": "quest_completion",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "quest_id": "456e4567-e89b-12d3-a456-426614174000",
                "amount": 50.00,
                "payment_method": "stripe",
                "notes": "Quest completion bonus"
            }
        }
    }


class TransactionResponse(BaseModel):
    """Schema for transaction response"""
    id: UUID
    transaction_type: TransactionType
    user_id: UUID
    quest_id: Optional[UUID]
    listing_id: Optional[UUID]
    amount: Decimal
    currency: str
    payment_method: PaymentMethod
    payment_status: PaymentStatus
    commission_amount: Optional[Decimal]
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "transaction_type": "quest_completion",
                "user_id": "456e4567-e89b-12d3-a456-426614174000",
                "amount": 50.00,
                "currency": "BDT",
                "payment_method": "stripe",
                "payment_status": "completed"
            }
        }
    }


class TransactionList(BaseModel):
    """Schema for paginated transaction list"""
    items: List[TransactionResponse]
    total: int
    skip: int
    limit: int
