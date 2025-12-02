from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import get_async_session
from app.core.auth import get_current_active_user, require_kabadiwala
from app.models.user import User
from app.models.listing import Listing, ListingStatus
from app.models.bid import Bid, BidStatus
from app.models.chat import Chat, ChatStatus
from app.schemas.bid import BidCreate, BidUpdate, BidResponse
from app.services.qr_service import get_qr_service
from decimal import Decimal
from pydantic import BaseModel, Field

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

    # Validate bid amount
    # If base_price is set (from ML prediction), use that as minimum
    if listing.base_price is not None:
        if bid_data.offered_price < listing.base_price:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Bid amount (Tk {bid_data.offered_price}) cannot be below the base price (Tk {listing.base_price})",
            )
    else:
        # Otherwise, require bid to be at least 50% of the estimated minimum value
        # This prevents unreasonably low bids like Tk 1 for a device worth Tk 5000+
        minimum_acceptable_bid = listing.estimated_value_min * Decimal("0.5")
        if bid_data.offered_price < minimum_acceptable_bid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Bid amount (Tk {bid_data.offered_price}) is too low. Minimum acceptable bid is Tk {minimum_acceptable_bid:.2f} (50% of estimated minimum value Tk {listing.estimated_value_min})",
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
    await session.refresh(bid, ["kabadiwala"])

    return bid


@router.get("/listing/{listing_id}", response_model=List[BidResponse])
async def get_bids_for_listing(
    listing_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Get all bids for a specific listing

    - Seller sees ALL bids on their listing
    - Kabadiwala sees ONLY their own bid on this listing
    - Admin sees all bids
    """
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

    # Determine what bids user can see
    is_seller = listing.seller_id == current_user.id
    is_admin = current_user.user_type.value == "admin"
    is_kabadiwala = current_user.user_type.value == "kabadiwala"

    # Build query based on authorization
    if is_seller or is_admin:
        # Seller and admin can see all bids
        result = await session.execute(
            select(Bid)
            .options(selectinload(Bid.kabadiwala))
            .where(Bid.listing_id == listing_id)
            .order_by(Bid.created_at.desc())
        )
    elif is_kabadiwala:
        # Kabadiwala can only see their own bid
        result = await session.execute(
            select(Bid)
            .options(selectinload(Bid.kabadiwala))
            .where(
                Bid.listing_id == listing_id,
                Bid.kabadiwala_id == current_user.id
            )
            .order_by(Bid.created_at.desc())
        )
    else:
        # Regular citizens cannot view bids
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view bids for this listing",
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
        .options(selectinload(Bid.kabadiwala))
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

    # Create or get chat for this transaction
    chat_result = await session.execute(
        select(Chat).where(
            Chat.listing_id == listing.id,
            Chat.buyer_id == bid.kabadiwala_id
        )
    )
    existing_chat = chat_result.scalar_one_or_none()

    if not existing_chat:
        # Create new chat (UNLOCKED for immediate messaging)
        chat = Chat(
            listing_id=listing.id,
            seller_id=listing.seller_id,
            buyer_id=bid.kabadiwala_id,
            status=ChatStatus.UNLOCKED
        )
        session.add(chat)

    await session.commit()
    await session.refresh(bid, ["kabadiwala"])

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


# QR Code schemas for weight confirmation
class QRGenerateRequest(BaseModel):
    """Request to generate QR code for weight confirmation"""
    listing_id: UUID


class QRGenerateResponse(BaseModel):
    """Response with QR code data"""
    qr_code_url: str = Field(description="Base64 encoded QR code image")
    qr_data: str = Field(description="Raw QR code data string")
    expires_at: Optional[str] = Field(None, description="Expiration timestamp")


class WeightConfirmRequest(BaseModel):
    """Request to confirm weight via QR scan"""
    qr_data: str = Field(description="Scanned QR code data")
    weight_kg: Decimal = Field(ge=0.01, le=9999.99, description="Confirmed weight in kg")


class WeightConfirmResponse(BaseModel):
    """Response after weight confirmation"""
    listing_id: UUID
    weight_kg: Decimal
    weight_verified: bool
    message: str


@router.post("/{bid_id}/generate-pickup-qr", response_model=QRGenerateResponse)
async def generate_pickup_qr(
    bid_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Generate QR code for kabadiwala to scan during pickup.
    This QR will be used for weight confirmation workflow.
    """
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

    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found",
        )

    # Only seller or accepted kabadiwala can generate QR
    if listing.seller_id != current_user.id and bid.kabadiwala_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to generate QR for this bid",
        )

    # Bid must be accepted
    if bid.status != BidStatus.ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only generate QR for accepted bids",
        )

    # Generate QR code
    qr_service = get_qr_service()
    qr_result = qr_service.generate_transaction_qr(
        transaction_id=str(bid.id),
        listing_id=str(listing.id),
        amount=float(bid.offered_price)
    )

    return QRGenerateResponse(
        qr_code_url=qr_result["qr_code_url"],
        qr_data=qr_result["qr_data"],
        expires_at=qr_result.get("expires_at")
    )


@router.post("/confirm-weight", response_model=WeightConfirmResponse)
async def confirm_weight_via_qr(
    weight_data: WeightConfirmRequest,
    confirm_excessive_weight: bool = Query(False, description="Flag to confirm weight even if it exceeds limits"),
    current_user: User = Depends(require_kabadiwala),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Kabadiwala scans QR code and confirms the weight of e-waste during pickup.
    This marks the listing as picked up with verified weight.
    """
    qr_service = get_qr_service()

    # Parse QR data
    parsed_qr = qr_service.parse_qr_data(weight_data.qr_data)

    if not parsed_qr or parsed_qr.get("type") != "transaction":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid QR code data",
        )

    listing_id = UUID(parsed_qr["listing_id"])
    bid_id = UUID(parsed_qr["transaction_id"])

    # Get listing
    listing_result = await session.execute(
        select(Listing).where(Listing.id == listing_id)
    )
    listing = listing_result.scalar_one_or_none()

    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found",
        )

    # Get bid
    bid_result = await session.execute(select(Bid).where(Bid.id == bid_id))
    bid = bid_result.scalar_one_or_none()

    if not bid:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bid not found",
        )

    # Verify kabadiwala is the one who won the bid
    if bid.kabadiwala_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the winning kabadiwala can confirm weight",
        )

    # Verify bid is accepted
    if bid.status != BidStatus.ACCEPTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This bid is not accepted",
        )

    # Weight Verification Logic
    # Define reasonable weight ranges (in kg)
    WEIGHT_LIMITS = {
        "laptop": {"max": 3.0},
        "monitor": {"max": 12.0},
        "mobile": {"max": 0.2},
        "tablet": {"max": 0.8},
        "desktop": {"max": 15.0},
    }

    device_type = listing.device_type.value
    weight_limit = WEIGHT_LIMITS.get(device_type, {}).get("max")

    message = f"Weight confirmed: {weight_data.weight_kg} kg. Listing marked as picked up."

    if weight_limit:
        # Check if weight is > 20% above max
        threshold = Decimal(str(weight_limit)) * Decimal("1.2")
        if weight_data.weight_kg > threshold:
            if not confirm_excessive_weight:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Reported weight ({weight_data.weight_kg} kg) is significantly above average for this device type (max expected ~{weight_limit} kg). Please confirm if this is correct.",
                )
            else:
                message += f" (Note: Weight exceeded average limit of {weight_limit} kg)"

    # Update listing with weight and mark as picked up
    listing.weight_kg = weight_data.weight_kg
    listing.weight_verified = True
    listing.status = ListingStatus.PICKED_UP

    await session.commit()
    await session.refresh(listing)

    return WeightConfirmResponse(
        listing_id=listing.id,
        weight_kg=listing.weight_kg,
        weight_verified=listing.weight_verified,
        message=message
    )
