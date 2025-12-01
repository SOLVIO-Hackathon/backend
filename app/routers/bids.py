from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_async_session
from app.core.auth import get_current_active_user, require_kabadiwala
from app.models.user import User
from app.models.listing import Listing, ListingStatus
from app.models.bid import Bid, BidStatus
from app.schemas.bid import BidCreate, BidUpdate, BidResponse

router = APIRouter(prefix="/bids", tags=["FlashTrade - Bids"])


@router.post("", response_model=BidResponse, status_code=status.HTTP_201_CREATED)
async def create_bid(
    bid_data: BidCreate,
    current_user: User = Depends(require_kabadiwala),
    session: AsyncSession = Depends(get_async_session),
):
    """Kabadiwala creates a bid on a listing"""
    # Check if listing exists
    result = await session.execute(
        select(Listing).where(Listing.id == bid_data.listing_id)
    )
    listing = result.scalar_one_or_none()

    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found",
        )

    if listing.status not in [ListingStatus.LISTED, ListingStatus.BIDDING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Listing is not accepting bids",
        )

    # Create bid
    bid = Bid(
        listing_id=bid_data.listing_id,
        kabadiwala_id=current_user.id,
        offered_price=bid_data.offered_price,
        pickup_time_estimate=bid_data.pickup_time_estimate,
        message=bid_data.message,
    )

    # Update listing status to BIDDING
    if listing.status == ListingStatus.LISTED:
        listing.status = ListingStatus.BIDDING

    session.add(bid)
    await session.commit()
    await session.refresh(bid)

    return bid


@router.get("/listing/{listing_id}", response_model=List[BidResponse])
async def get_bids_for_listing(
    listing_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Get all bids for a specific listing"""
    # Check if listing exists and user has access
    listing_result = await session.execute(
        select(Listing).where(Listing.id == listing_id)
    )
    listing = listing_result.scalar_one_or_none()

    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found",
        )

    # Only seller can see all bids
    if listing.seller_id != current_user.id and current_user.user_type.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view bids for this listing",
        )

    # Get bids
    result = await session.execute(
        select(Bid)
        .where(Bid.listing_id == listing_id)
        .order_by(Bid.created_at.desc())
    )
    bids = result.scalars().all()

    return bids


@router.get("/my-bids", response_model=List[BidResponse])
async def get_my_bids(
    current_user: User = Depends(require_kabadiwala),
    session: AsyncSession = Depends(get_async_session),
):
    """Get all bids created by current kabadiwala"""
    result = await session.execute(
        select(Bid)
        .where(Bid.kabadiwala_id == current_user.id)
        .order_by(Bid.created_at.desc())
    )
    bids = result.scalars().all()

    return bids


@router.patch("/{bid_id}/accept", response_model=BidResponse)
async def accept_bid(
    bid_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Seller accepts a bid"""
    # Get bid
    result = await session.execute(select(Bid).where(Bid.id == bid_id))
    bid = result.scalar_one_or_none()

    if not bid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bid not found",
        )

    # Get listing
    listing_result = await session.execute(
        select(Listing).where(Listing.id == bid.listing_id)
    )
    listing = listing_result.scalar_one_or_none()

    # Check if user is the seller
    if listing.seller_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the seller can accept bids",
        )

    # Accept bid
    bid.status = BidStatus.ACCEPTED
    listing.status = ListingStatus.ACCEPTED
    listing.buyer_id = bid.kabadiwala_id
    listing.final_price = bid.offered_price

    await session.commit()
    await session.refresh(bid)

    return bid


@router.delete("/{bid_id}", status_code=status.HTTP_204_NO_CONTENT)
async def withdraw_bid(
    bid_id: UUID,
    current_user: User = Depends(require_kabadiwala),
    session: AsyncSession = Depends(get_async_session),
):
    """Kabadiwala withdraws their bid"""
    result = await session.execute(select(Bid).where(Bid.id == bid_id))
    bid = result.scalar_one_or_none()

    if not bid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bid not found",
        )

    if bid.kabadiwala_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only withdraw your own bids",
        )

    if bid.status != BidStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only withdraw pending bids",
        )

    bid.status = BidStatus.WITHDRAWN
    await session.commit()
