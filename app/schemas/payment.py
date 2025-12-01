from typing import Optional
from uuid import UUID
from decimal import Decimal
from pydantic import BaseModel, Field


class StripePaymentIntentCreate(BaseModel):
    """Schema for creating a Stripe payment intent"""
    amount: Decimal = Field(..., gt=0, description="Amount in your currency (e.g., BDT)")
    currency: str = Field(default="usd", description="Currency code (e.g., usd, eur)")
    description: Optional[str] = Field(None, description="Payment description")
    metadata: Optional[dict] = Field(default_factory=dict, description="Additional metadata")

    model_config = {
        "json_schema_extra": {
            "example": {
                "amount": 100.00,
                "currency": "usd",
                "description": "Payment for quest completion",
                "metadata": {
                    "quest_id": "123e4567-e89b-12d3-a456-426614174000",
                    "user_id": "456e4567-e89b-12d3-a456-426614174000"
                }
            }
        }
    }


class StripePaymentIntentResponse(BaseModel):
    """Schema for Stripe payment intent response"""
    payment_intent_id: str
    client_secret: str
    amount: int
    currency: str
    status: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "payment_intent_id": "pi_1234567890",
                "client_secret": "pi_1234567890_secret_abcdefg",
                "amount": 10000,
                "currency": "usd",
                "status": "requires_payment_method"
            }
        }
    }


class StripeCheckoutSessionCreate(BaseModel):
    """Schema for creating a Stripe checkout session"""
    amount: Decimal = Field(..., gt=0, description="Amount in your currency")
    currency: str = Field(default="usd", description="Currency code")
    success_url: str = Field(..., description="URL to redirect on success")
    cancel_url: str = Field(..., description="URL to redirect on cancel")
    description: Optional[str] = Field(None, description="Payment description")
    metadata: Optional[dict] = Field(default_factory=dict, description="Additional metadata")

    model_config = {
        "json_schema_extra": {
            "example": {
                "amount": 100.00,
                "currency": "usd",
                "success_url": "https://yourapp.com/payment/success",
                "cancel_url": "https://yourapp.com/payment/cancel",
                "description": "E-waste purchase",
                "metadata": {
                    "listing_id": "123e4567-e89b-12d3-a456-426614174000"
                }
            }
        }
    }


class StripeCheckoutSessionResponse(BaseModel):
    """Schema for Stripe checkout session response"""
    session_id: str
    url: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "session_id": "cs_test_1234567890",
                "url": "https://checkout.stripe.com/pay/cs_test_1234567890"
            }
        }
    }


class StripeWebhookEvent(BaseModel):
    """Schema for Stripe webhook event"""
    event_type: str
    payment_intent_id: Optional[str] = None
    checkout_session_id: Optional[str] = None
    amount: Optional[int] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    metadata: Optional[dict] = None


class PublishableKeyResponse(BaseModel):
    """Schema for Stripe publishable key response"""
    publishable_key: str
