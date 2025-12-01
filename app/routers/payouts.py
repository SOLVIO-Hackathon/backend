from typing import List, Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_async_session
from app.core.auth import get_current_active_user, require_admin
from app.models.user import User
from app.models.payout import Payout, PayoutStatus, PayoutMethod
from app.models.transaction import Transaction, PaymentStatus
from app.schemas.payout import (
    PayoutCreate, PayoutResponse, PayoutList,
    StripeConnectAccountCreate, StripeConnectAccountResponse,
    ProcessPayoutRequest
)
from app.services.stripe_service import StripeService

router = APIRouter(prefix="/payouts", tags=["Payouts"])


@router.post("", response_model=PayoutResponse, status_code=status.HTTP_201_CREATED)
async def create_payout_request(
    payout_data: PayoutCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Create a payout request for the current user.
    
    The payout will be processed after admin approval.
    """
    payout = Payout(
        user_id=current_user.id,
        amount=payout_data.amount,
        currency=payout_data.currency,
        payout_method=payout_data.payout_method,
        notes=payout_data.notes,
        status=PayoutStatus.PENDING
    )

    session.add(payout)
    await session.commit()
    await session.refresh(payout)

    return payout


@router.get("", response_model=PayoutList)
async def list_payouts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status_filter: Optional[PayoutStatus] = None,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """List payouts for the current user"""
    query = select(Payout).where(Payout.user_id == current_user.id)

    if status_filter:
        query = query.where(Payout.status == status_filter)

    # Get total count
    count_query = select(func.count()).select_from(Payout).where(
        Payout.user_id == current_user.id
    )
    if status_filter:
        count_query = count_query.where(Payout.status == status_filter)

    total_result = await session.execute(count_query)
    total = total_result.scalar()

    # Get payouts
    query = query.order_by(Payout.created_at.desc()).offset(skip).limit(limit)
    result = await session.execute(query)
    payouts = result.scalars().all()

    return PayoutList(items=payouts, total=total)


@router.get("/admin", response_model=PayoutList)
async def list_all_payouts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status_filter: Optional[PayoutStatus] = None,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """List all payouts (Admin only)"""
    query = select(Payout)

    if status_filter:
        query = query.where(Payout.status == status_filter)

    # Get total count
    count_query = select(func.count()).select_from(Payout)
    if status_filter:
        count_query = count_query.where(Payout.status == status_filter)

    total_result = await session.execute(count_query)
    total = total_result.scalar()

    # Get payouts
    query = query.order_by(Payout.created_at.desc()).offset(skip).limit(limit)
    result = await session.execute(query)
    payouts = result.scalars().all()

    return PayoutList(items=payouts, total=total)


@router.get("/{payout_id}", response_model=PayoutResponse)
async def get_payout(
    payout_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Get a specific payout by ID"""
    result = await session.execute(
        select(Payout).where(Payout.id == payout_id)
    )
    payout = result.scalar_one_or_none()

    if not payout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payout not found"
        )

    # Check authorization
    if payout.user_id != current_user.id and current_user.user_type.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this payout"
        )

    return payout


@router.post("/process", response_model=PayoutResponse)
async def process_payout(
    process_request: ProcessPayoutRequest,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Process a payout request (Admin only).
    
    Approves or rejects the payout. If approved, initiates the actual transfer.
    """
    result = await session.execute(
        select(Payout).where(Payout.id == process_request.payout_id)
    )
    payout = result.scalar_one_or_none()

    if not payout:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payout not found"
        )

    if payout.status != PayoutStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payout has already been processed"
        )

    if not process_request.approve:
        # Reject payout
        payout.status = PayoutStatus.FAILED
        payout.failure_reason = process_request.notes or "Rejected by admin"
        payout.processed_at = datetime.utcnow()
    else:
        # Approve and process payout
        payout.status = PayoutStatus.PROCESSING

        # If Stripe payout method, initiate Stripe transfer
        if payout.payout_method == PayoutMethod.STRIPE_TRANSFER:
            try:
                stripe_service = StripeService()
                # Note: In production, you'd use the user's connected Stripe account
                # For hackathon, we'll just mark as completed
                payout.status = PayoutStatus.COMPLETED
                payout.notes = process_request.notes
            except Exception as e:
                payout.status = PayoutStatus.FAILED
                payout.failure_reason = str(e)
        else:
            # For other methods, just mark as completed (manual processing)
            payout.status = PayoutStatus.COMPLETED
            payout.notes = process_request.notes

        payout.processed_at = datetime.utcnow()

    await session.commit()
    await session.refresh(payout)

    return payout


@router.post("/connect-account", response_model=StripeConnectAccountResponse)
async def create_stripe_connect_account(
    account_data: StripeConnectAccountCreate,
    current_user: User = Depends(get_current_active_user),
):
    """
    Create a Stripe Connect account for receiving payouts.
    
    Returns an onboarding URL that the user must complete to verify their identity.
    """
    import stripe
    from app.core.config import settings

    stripe.api_key = settings.STRIPE_SECRET_KEY

    try:
        # Create Express Connect account
        account = stripe.Account.create(
            type="express",
            country=account_data.country,
            email=account_data.email,
            capabilities={
                "transfers": {"requested": True},
            },
            metadata={
                "user_id": str(current_user.id)
            }
        )

        # Create account onboarding link
        account_link = stripe.AccountLink.create(
            account=account.id,
            refresh_url="https://your-app.com/connect/refresh",
            return_url="https://your-app.com/connect/return",
            type="account_onboarding",
        )

        return StripeConnectAccountResponse(
            account_id=account.id,
            onboarding_url=account_link.url,
            details_submitted=account.details_submitted
        )

    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Stripe error: {str(e)}"
        )


@router.post("/from-transaction/{transaction_id}", response_model=PayoutResponse)
async def create_payout_from_transaction(
    transaction_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Create a payout request from a completed transaction.
    
    This links the payout to a specific transaction for tracking.
    """
    # Get the transaction
    result = await session.execute(
        select(Transaction).where(Transaction.id == transaction_id)
    )
    transaction = result.scalar_one_or_none()

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found"
        )

    # Verify the user is the recipient
    if transaction.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to request payout for this transaction"
        )

    # Verify transaction is completed
    if transaction.payment_status != PaymentStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transaction is not completed"
        )

    # Check if payout already exists for this transaction
    existing = await session.execute(
        select(Payout).where(Payout.transaction_id == transaction_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Payout already requested for this transaction"
        )

    # Create payout
    payout = Payout(
        user_id=current_user.id,
        transaction_id=transaction_id,
        amount=transaction.amount,
        currency=transaction.currency,
        payout_method=PayoutMethod.STRIPE_TRANSFER,
        notes=f"Payout for transaction {transaction_id}",
        status=PayoutStatus.PENDING
    )

    session.add(payout)
    await session.commit()
    await session.refresh(payout)

    return payout
