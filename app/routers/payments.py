from typing import Optional
from fastapi import APIRouter, HTTPException, Header, Request, Depends, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_session
from app.services.stripe_service import StripeService
from app.schemas.payment import (
    StripePaymentIntentCreate,
    StripePaymentIntentResponse,
    StripeCheckoutSessionCreate,
    StripeCheckoutSessionResponse,
    PublishableKeyResponse,
)
from app.models.user import User
from app.models.transaction import Transaction, PaymentStatus, TransactionType, PaymentMethod
from app.models.quest import Quest, QuestStatus
from app.models.listing import Listing, ListingStatus
from app.core.auth import get_current_active_user
from uuid import UUID
from sqlalchemy import select

router = APIRouter(prefix="/payments", tags=["Payments"])
stripe_service = StripeService()


@router.get("/config", response_model=PublishableKeyResponse)
async def get_stripe_config():
    """
    Get Stripe publishable key for client-side integration
    """
    return PublishableKeyResponse(
        publishable_key=settings.STRIPE_PUBLISHABLE_KEY
    )


@router.post("/create-payment-intent", response_model=StripePaymentIntentResponse)
async def create_payment_intent(
    payment_data: StripePaymentIntentCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session)
):
    """
    Create a Stripe Payment Intent for processing payments

    This endpoint creates a payment intent that can be used with Stripe's
    client-side libraries to collect payment information securely.

    **Required:**
    - Authentication token in header
    - amount: Payment amount in your currency
    - currency: Currency code (e.g., 'usd', 'eur')

    **Optional:**
    - description: Payment description
    - metadata: Additional data (quest_id, listing_id, etc.)

    **Returns:**
    - payment_intent_id: Stripe Payment Intent ID
    - client_secret: Secret for client-side confirmation
    - amount: Amount in smallest currency unit (cents)
    - currency: Currency code
    - status: Payment intent status
    """
    # Add user_id to metadata
    metadata = payment_data.metadata or {}
    metadata["user_id"] = str(current_user.id)

    # Create payment intent
    payment_intent = stripe_service.create_payment_intent(
        amount=payment_data.amount,
        currency=payment_data.currency,
        description=payment_data.description,
        metadata=metadata
    )

    return StripePaymentIntentResponse(
        payment_intent_id=payment_intent.id,
        client_secret=payment_intent.client_secret,
        amount=payment_intent.amount,
        currency=payment_intent.currency,
        status=payment_intent.status
    )


@router.post("/create-checkout-session", response_model=StripeCheckoutSessionResponse)
async def create_checkout_session(
    session_data: StripeCheckoutSessionCreate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_session)
):
    """
    Create a Stripe Checkout Session for hosted payment page

    This endpoint creates a checkout session that redirects users to
    Stripe's hosted payment page for a seamless payment experience.

    **Required:**
    - Authentication token in header
    - amount: Payment amount
    - currency: Currency code
    - success_url: Redirect URL after successful payment
    - cancel_url: Redirect URL if payment is cancelled

    **Optional:**
    - description: Payment description
    - metadata: Additional data

    **Returns:**
    - session_id: Checkout Session ID
    - url: Stripe Checkout URL to redirect user to
    """
    # Add user_id to metadata
    metadata = session_data.metadata or {}
    metadata["user_id"] = str(current_user.id)

    # Create checkout session
    session = stripe_service.create_checkout_session(
        amount=session_data.amount,
        currency=session_data.currency,
        success_url=session_data.success_url,
        cancel_url=session_data.cancel_url,
        description=session_data.description,
        metadata=metadata
    )

    return StripeCheckoutSessionResponse(
        session_id=session.id,
        url=session.url
    )


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(None, alias="stripe-signature"),
    db: Session = Depends(get_session)
):
    """
    Stripe webhook endpoint for handling payment events

    This endpoint receives events from Stripe about payment status changes.
    Configure this URL in your Stripe Dashboard under Webhooks.

    **Webhook URL:** https://your-domain.com/api/v1/payments/webhook

    **Important Events:**
    - payment_intent.succeeded: Payment completed successfully
    - payment_intent.payment_failed: Payment failed
    - checkout.session.completed: Checkout session completed
    - charge.refunded: Payment refunded

    **Note:** This endpoint does not require authentication as it's called by Stripe
    """
    if not stripe_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing stripe-signature header"
        )

    # Get raw body
    payload = await request.body()

    # Verify and construct event
    event = stripe_service.construct_webhook_event(
        payload=payload,
        signature=stripe_signature
    )

    # Handle different event types
    event_type = event["type"]
    event_data = event["data"]["object"]

    if event_type == "payment_intent.succeeded":
        # Handle successful payment
        payment_intent_id = event_data["id"]
        amount = event_data["amount"]
        currency = event_data.get("currency", "usd")
        metadata = event_data.get("metadata", {})

        # Find and update transaction in database
        result = db.execute(
            select(Transaction).where(Transaction.stripe_payment_intent_id == payment_intent_id)
        )
        transaction = result.scalar_one_or_none()

        if transaction:
            # Update transaction status to completed
            transaction.payment_status = PaymentStatus.COMPLETED
            db.commit()
            db.refresh(transaction)

            # Update quest/listing status if applicable
            if transaction.quest_id:
                # Update quest status to completed (payment received)
                quest_result = db.execute(
                    select(Quest).where(Quest.id == transaction.quest_id)
                )
                quest = quest_result.scalar_one_or_none()
                if quest and quest.status == QuestStatus.VERIFIED:
                    quest.status = QuestStatus.COMPLETED
                    db.commit()

            elif transaction.listing_id:
                # Update listing status to completed (payment received)
                listing_result = db.execute(
                    select(Listing).where(Listing.id == transaction.listing_id)
                )
                listing = listing_result.scalar_one_or_none()
                if listing and listing.status == ListingStatus.PICKED_UP:
                    listing.status = ListingStatus.COMPLETED
                    db.commit()

            print(f"✅ Payment succeeded: {payment_intent_id} - Amount: {amount/100} {currency.upper()}")
            print(f"   Transaction {transaction.id} marked as COMPLETED")
        else:
            # Create new transaction record if it doesn't exist
            user_id = metadata.get("user_id")
            if user_id:
                try:
                    # Determine transaction type from metadata
                    transaction_type = TransactionType.E_WASTE_SALE
                    quest_id = metadata.get("quest_id")
                    listing_id = metadata.get("listing_id")

                    if quest_id:
                        transaction_type = TransactionType.QUEST_COMPLETION

                    new_transaction = Transaction(
                        transaction_type=transaction_type,
                        user_id=UUID(user_id),
                        quest_id=UUID(quest_id) if quest_id else None,
                        listing_id=UUID(listing_id) if listing_id else None,
                        amount=amount / 100,  # Convert from cents
                        currency=currency.upper(),
                        payment_method=PaymentMethod.STRIPE,
                        payment_status=PaymentStatus.COMPLETED,
                        stripe_payment_intent_id=payment_intent_id,
                        notes=f"Payment completed via Stripe webhook"
                    )
                    db.add(new_transaction)
                    db.commit()
                    print(f"✅ Created new transaction record for payment: {payment_intent_id}")
                except Exception as e:
                    print(f"❌ Error creating transaction record: {e}")
                    db.rollback()

    elif event_type == "payment_intent.payment_failed":
        # Handle failed payment
        payment_intent_id = event_data["id"]
        error_message = event_data.get("last_payment_error", {}).get("message", "Unknown error")
        metadata = event_data.get("metadata", {})

        # Find and update transaction in database
        result = db.execute(
            select(Transaction).where(Transaction.stripe_payment_intent_id == payment_intent_id)
        )
        transaction = result.scalar_one_or_none()

        if transaction:
            # Update transaction status to failed
            transaction.payment_status = PaymentStatus.FAILED
            transaction.notes = f"Payment failed: {error_message}"
            db.commit()
            db.refresh(transaction)

            print(f"❌ Payment failed: {payment_intent_id}")
            print(f"   Transaction {transaction.id} marked as FAILED")
            print(f"   Error: {error_message}")
        else:
            # Create failed transaction record
            user_id = metadata.get("user_id")
            if user_id:
                try:
                    transaction_type = TransactionType.E_WASTE_SALE
                    quest_id = metadata.get("quest_id")
                    listing_id = metadata.get("listing_id")

                    if quest_id:
                        transaction_type = TransactionType.QUEST_COMPLETION

                    new_transaction = Transaction(
                        transaction_type=transaction_type,
                        user_id=UUID(user_id),
                        quest_id=UUID(quest_id) if quest_id else None,
                        listing_id=UUID(listing_id) if listing_id else None,
                        amount=event_data.get("amount", 0) / 100,
                        currency=event_data.get("currency", "BDT").upper(),
                        payment_method=PaymentMethod.STRIPE,
                        payment_status=PaymentStatus.FAILED,
                        stripe_payment_intent_id=payment_intent_id,
                        notes=f"Payment failed: {error_message}"
                    )
                    db.add(new_transaction)
                    db.commit()
                    print(f"❌ Created failed transaction record: {payment_intent_id}")
                except Exception as e:
                    print(f"❌ Error creating failed transaction record: {e}")
                    db.rollback()

    elif event_type == "checkout.session.completed":
        # Handle completed checkout session
        session_id = event_data["id"]
        payment_intent_id = event_data.get("payment_intent")
        amount = event_data.get("amount_total", 0)
        currency = event_data.get("currency", "BDT")
        metadata = event_data.get("metadata", {})

        # Find transaction by checkout session ID
        result = db.execute(
            select(Transaction).where(Transaction.stripe_checkout_session_id == session_id)
        )
        transaction = result.scalar_one_or_none()

        if transaction:
            # Update transaction with payment intent ID and mark as completed
            transaction.stripe_payment_intent_id = payment_intent_id
            transaction.payment_status = PaymentStatus.COMPLETED
            db.commit()
            db.refresh(transaction)

            # Update quest/listing status
            if transaction.quest_id:
                quest_result = db.execute(
                    select(Quest).where(Quest.id == transaction.quest_id)
                )
                quest = quest_result.scalar_one_or_none()
                if quest and quest.status == QuestStatus.VERIFIED:
                    quest.status = QuestStatus.COMPLETED
                    db.commit()

            elif transaction.listing_id:
                listing_result = db.execute(
                    select(Listing).where(Listing.id == transaction.listing_id)
                )
                listing = listing_result.scalar_one_or_none()
                if listing and listing.status == ListingStatus.PICKED_UP:
                    listing.status = ListingStatus.COMPLETED
                    db.commit()

            print(f"✅ Checkout completed: {session_id}")
            print(f"   Transaction {transaction.id} marked as COMPLETED")
            print(f"   Payment Intent: {payment_intent_id}")
        else:
            # Create new transaction from checkout session
            user_id = metadata.get("user_id")
            if user_id:
                try:
                    transaction_type = TransactionType.E_WASTE_SALE
                    quest_id = metadata.get("quest_id")
                    listing_id = metadata.get("listing_id")

                    if quest_id:
                        transaction_type = TransactionType.QUEST_COMPLETION

                    new_transaction = Transaction(
                        transaction_type=transaction_type,
                        user_id=UUID(user_id),
                        quest_id=UUID(quest_id) if quest_id else None,
                        listing_id=UUID(listing_id) if listing_id else None,
                        amount=amount / 100,
                        currency=currency.upper(),
                        payment_method=PaymentMethod.STRIPE,
                        payment_status=PaymentStatus.COMPLETED,
                        stripe_payment_intent_id=payment_intent_id,
                        stripe_checkout_session_id=session_id,
                        notes="Payment completed via Stripe Checkout"
                    )
                    db.add(new_transaction)
                    db.commit()
                    print(f"✅ Created transaction from checkout: {session_id}")
                except Exception as e:
                    print(f"❌ Error creating transaction from checkout: {e}")
                    db.rollback()

    elif event_type == "charge.refunded":
        # Handle refund
        charge_id = event_data["id"]
        amount_refunded = event_data["amount_refunded"]
        payment_intent_id = event_data.get("payment_intent")
        currency = event_data.get("currency", "BDT")

        # Find transaction by payment intent
        if payment_intent_id:
            result = db.execute(
                select(Transaction).where(Transaction.stripe_payment_intent_id == payment_intent_id)
            )
            transaction = result.scalar_one_or_none()

            if transaction:
                # Update transaction status to refunded
                transaction.payment_status = PaymentStatus.REFUNDED
                transaction.notes = f"Refunded: {amount_refunded / 100} {currency.upper()}"
                db.commit()
                db.refresh(transaction)

                # Optionally revert quest/listing status
                if transaction.quest_id:
                    quest_result = db.execute(
                        select(Quest).where(Quest.id == transaction.quest_id)
                    )
                    quest = quest_result.scalar_one_or_none()
                    if quest and quest.status == QuestStatus.COMPLETED:
                        quest.status = QuestStatus.VERIFIED  # Revert to verified
                        db.commit()

                elif transaction.listing_id:
                    listing_result = db.execute(
                        select(Listing).where(Listing.id == transaction.listing_id)
                    )
                    listing = listing_result.scalar_one_or_none()
                    if listing and listing.status == ListingStatus.COMPLETED:
                        listing.status = ListingStatus.PICKED_UP  # Revert to picked up
                        db.commit()

                print(f"💰 Refund processed: {charge_id}")
                print(f"   Transaction {transaction.id} marked as REFUNDED")
                print(f"   Amount: {amount_refunded / 100} {currency.upper()}")
            else:
                print(f"💰 Refund processed but no matching transaction found: {charge_id}")
        else:
            print(f"💰 Refund processed without payment intent: {charge_id}")

    else:
        print(f"ℹ️ Unhandled event type: {event_type}")

    return {"status": "success", "event_type": event_type}


@router.get("/payment-intent/{payment_intent_id}")
async def get_payment_intent(
    payment_intent_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieve a Payment Intent by ID

    **Required:**
    - Authentication token
    - payment_intent_id: The Stripe Payment Intent ID

    **Returns:**
    - Full Payment Intent object from Stripe
    """
    payment_intent = stripe_service.retrieve_payment_intent(payment_intent_id)

    # Verify user owns this payment intent
    metadata = payment_intent.get("metadata", {})
    if metadata.get("user_id") != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this payment intent"
        )

    return {
        "payment_intent_id": payment_intent.id,
        "amount": payment_intent.amount,
        "currency": payment_intent.currency,
        "status": payment_intent.status,
        "metadata": payment_intent.metadata
    }


@router.post("/cancel-payment-intent/{payment_intent_id}")
async def cancel_payment_intent(
    payment_intent_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Cancel a Payment Intent

    **Required:**
    - Authentication token
    - payment_intent_id: The Payment Intent ID to cancel

    **Returns:**
    - Cancelled Payment Intent details
    """
    # Retrieve to verify ownership
    payment_intent = stripe_service.retrieve_payment_intent(payment_intent_id)
    metadata = payment_intent.get("metadata", {})

    if metadata.get("user_id") != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to cancel this payment intent"
        )

    # Cancel the payment intent
    cancelled_payment_intent = stripe_service.cancel_payment_intent(payment_intent_id)

    return {
        "payment_intent_id": cancelled_payment_intent.id,
        "status": cancelled_payment_intent.status,
        "message": "Payment intent cancelled successfully"
    }
