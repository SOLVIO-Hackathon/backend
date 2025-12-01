from typing import Optional, List
from datetime import datetime
from uuid import UUID
from decimal import Decimal
from pydantic import BaseModel, Field

from app.models.payout import PayoutStatus, PayoutMethod


class PayoutCreate(BaseModel):
    """Schema for creating a payout request"""
    amount: Decimal = Field(..., gt=0)
    currency: str = Field(default="USD")
    payout_method: PayoutMethod
    notes: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "amount": 50.00,
                "currency": "USD",
                "payout_method": "stripe_transfer",
                "notes": "Quest completion payout"
            }
        }
    }


class PayoutResponse(BaseModel):
    """Schema for payout response"""
    id: UUID
    user_id: UUID
    transaction_id: Optional[UUID]
    amount: Decimal
    currency: str
    payout_method: PayoutMethod
    status: PayoutStatus
    stripe_transfer_id: Optional[str]
    bank_account_last4: Optional[str]
    notes: Optional[str]
    failure_reason: Optional[str]
    created_at: datetime
    processed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class PayoutList(BaseModel):
    """Schema for paginated payout list"""
    items: List[PayoutResponse]
    total: int


class StripeConnectAccountCreate(BaseModel):
    """Schema for creating a Stripe Connect account for payouts"""
    email: str = Field(..., description="User's email for Stripe account")
    country: str = Field(default="US", description="Two-letter country code")

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "seller@example.com",
                "country": "US"
            }
        }
    }


class StripeConnectAccountResponse(BaseModel):
    """Schema for Stripe Connect account response"""
    account_id: str
    onboarding_url: str
    details_submitted: bool


class ProcessPayoutRequest(BaseModel):
    """Schema for processing a payout (admin)"""
    payout_id: UUID
    approve: bool = Field(..., description="True to approve, False to reject")
    notes: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "payout_id": "123e4567-e89b-12d3-a456-426614174000",
                "approve": True,
                "notes": "Verified and processed"
            }
        }
    }
