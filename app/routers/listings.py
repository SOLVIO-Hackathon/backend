from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_async_session
from app.core.auth import get_current_active_user, require_kabadiwala
from app.models.user import User
from app.models.listing import Listing, ListingStatus
from app.schemas.listing import ListingCreate, ListingUpdate, ListingResponse, ListingList

router = APIRouter(prefix="/listings", tags=["FlashTrade"])


@router.post("", response_model=ListingResponse, status_code=status.HTTP_201_CREATED)
async def create_listing(
    listing_data: ListingCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Create a new e-waste listing"""
    # TODO: Call AI service to estimate value
    estimated_min = 1000.0  # Placeholder
    estimated_max = 1500.0  # Placeholder

    listing = Listing(
        seller_id=current_user.id,
        device_type=listing_data.device_type,
        device_name=listing_data.device_name,
        condition=listing_data.condition,
        image_urls=listing_data.image_urls,
        description=listing_data.description,
        location=f"POINT({listing_data.location.longitude} {listing_data.location.latitude})",
        estimated_value_min=estimated_min,
        estimated_value_max=estimated_max,
    )

    session.add(listing)
    await session.commit()
    await session.refresh(listing)

    return listing


@router.get("", response_model=ListingList)
async def list_listings(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    status_filter: Optional[ListingStatus] = None,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """List all e-waste listings"""
    query = select(Listing)

    if status_filter:
        query = query.where(Listing.status == status_filter)

    # Get total count
    count_query = select(func.count()).select_from(Listing)
    if status_filter:
        count_query = count_query.where(Listing.status == status_filter)

    total_result = await session.execute(count_query)
    total = total_result.scalar()

    # Get listings
    query = query.offset(skip).limit(limit).order_by(Listing.created_at.desc())
    result = await session.execute(query)
    listings = result.scalars().all()

    return ListingList(items=listings, total=total, skip=skip, limit=limit)


@router.get("/{listing_id}", response_model=ListingResponse)
async def get_listing(
    listing_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Get a specific listing by ID"""
    result = await session.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()

    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found",
        )

    return listing


@router.patch("/{listing_id}", response_model=ListingResponse)
async def update_listing(
    listing_id: UUID,
    listing_update: ListingUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Update a listing"""
    result = await session.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()

    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found",
        )

    # Only seller can update their listing
    if listing.seller_id != current_user.id and current_user.user_type.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this listing",
        )

    # Update fields
    for field, value in listing_update.model_dump(exclude_unset=True).items():
        setattr(listing, field, value)

    await session.commit()
    await session.refresh(listing)

    return listing


@router.delete("/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_listing(
    listing_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Delete a listing (seller only)"""
    result = await session.execute(select(Listing).where(Listing.id == listing_id))
    listing = result.scalar_one_or_none()

    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found",
        )

    if listing.seller_id != current_user.id and current_user.user_type.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this listing",
        )

    await session.delete(listing)
    await session.commit()
