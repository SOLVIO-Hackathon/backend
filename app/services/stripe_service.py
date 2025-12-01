import stripe
from typing import Optional, Dict, Any
from decimal import Decimal
from fastapi import HTTPException, status

from app.core.config import settings

# Initialize Stripe with secret key
stripe.api_key = settings.STRIPE_SECRET_KEY


class StripeService:
    """Service for handling Stripe payment operations"""

    @staticmethod
    def create_payment_intent(
        amount: Decimal,
        currency: str = "usd",
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> stripe.PaymentIntent:
        """
        Create a Stripe Payment Intent

        Args:
            amount: Amount in currency (will be converted to smallest unit)
            currency: Currency code (default: usd)
            description: Payment description
            metadata: Additional metadata to attach to the payment

        Returns:
            Stripe PaymentIntent object
        """
        try:
            # Convert amount to smallest currency unit (cents for USD)
            amount_in_cents = int(amount * 100)

            payment_intent = stripe.PaymentIntent.create(
                amount=amount_in_cents,
                currency=currency.lower(),
                description=description,
                metadata=metadata or {},
                automatic_payment_methods={"enabled": True},
            )

            return payment_intent

        except stripe.error.StripeError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stripe error: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create payment intent: {str(e)}"
            )

    @staticmethod
    def create_checkout_session(
        amount: Decimal,
        currency: str = "usd",
        success_url: str = "",
        cancel_url: str = "",
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> stripe.checkout.Session:
        """
        Create a Stripe Checkout Session

        Args:
            amount: Amount in currency
            currency: Currency code
            success_url: URL to redirect on successful payment
            cancel_url: URL to redirect on cancelled payment
            description: Payment description
            metadata: Additional metadata

        Returns:
            Stripe Checkout Session object
        """
        try:
            # Convert amount to smallest currency unit
            amount_in_cents = int(amount * 100)

            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": currency.lower(),
                        "product_data": {
                            "name": description or "Payment",
                        },
                        "unit_amount": amount_in_cents,
                    },
                    "quantity": 1,
                }],
                mode="payment",
                success_url=success_url,
                cancel_url=cancel_url,
                metadata=metadata or {},
            )

            return session

        except stripe.error.StripeError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Stripe error: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create checkout session: {str(e)}"
            )

    @staticmethod
    def retrieve_payment_intent(payment_intent_id: str) -> stripe.PaymentIntent:
        """
        Retrieve a Stripe Payment Intent by ID

        Args:
            payment_intent_id: The Payment Intent ID

        Returns:
            Stripe PaymentIntent object
        """
        try:
            return stripe.PaymentIntent.retrieve(payment_intent_id)
        except stripe.error.StripeError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment intent not found: {str(e)}"
            )

    @staticmethod
    def retrieve_checkout_session(session_id: str) -> stripe.checkout.Session:
        """
        Retrieve a Stripe Checkout Session by ID

        Args:
            session_id: The Checkout Session ID

        Returns:
            Stripe Checkout Session object
        """
        try:
            return stripe.checkout.Session.retrieve(session_id)
        except stripe.error.StripeError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Checkout session not found: {str(e)}"
            )

    @staticmethod
    def construct_webhook_event(
        payload: bytes,
        signature: str,
        webhook_secret: Optional[str] = None
    ) -> stripe.Event:
        """
        Construct and verify a Stripe webhook event

        Args:
            payload: Raw request body
            signature: Stripe signature from headers
            webhook_secret: Webhook secret (defaults to settings)

        Returns:
            Verified Stripe Event object
        """
        secret = webhook_secret or settings.STRIPE_WEBHOOK_SECRET

        if not secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Webhook secret not configured"
            )

        try:
            event = stripe.Webhook.construct_event(
                payload, signature, secret
            )
            return event
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid payload"
            )
        except stripe.error.SignatureVerificationError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid signature"
            )

    @staticmethod
    def cancel_payment_intent(payment_intent_id: str) -> stripe.PaymentIntent:
        """
        Cancel a Stripe Payment Intent

        Args:
            payment_intent_id: The Payment Intent ID to cancel

        Returns:
            Cancelled Stripe PaymentIntent object
        """
        try:
            return stripe.PaymentIntent.cancel(payment_intent_id)
        except stripe.error.StripeError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to cancel payment intent: {str(e)}"
            )

    @staticmethod
    def create_refund(
        payment_intent_id: str,
        amount: Optional[int] = None,
        reason: Optional[str] = None
    ) -> stripe.Refund:
        """
        Create a refund for a payment

        Args:
            payment_intent_id: The Payment Intent ID to refund
            amount: Amount to refund in cents (None for full refund)
            reason: Reason for refund

        Returns:
            Stripe Refund object
        """
        try:
            refund_params = {"payment_intent": payment_intent_id}

            if amount is not None:
                refund_params["amount"] = amount

            if reason:
                refund_params["reason"] = reason

            return stripe.Refund.create(**refund_params)
        except stripe.error.StripeError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to create refund: {str(e)}"
            )
