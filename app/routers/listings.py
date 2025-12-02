from typing import Optional
from uuid import UUID
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
import pandas as pd
from decimal import Decimal

from app.core.database import get_async_session
from app.core.auth import get_current_active_user, require_kabadiwala
from app.models.user import User
from app.models.listing import Listing, ListingStatus, DeviceCondition
from app.schemas.listing import (
    ListingCreate,
    ListingUpdate,
    ListingResponse,
    ListingList,
)
from app.services.ai_service import get_ai_service
from app.services.price_prediction_service import get_predictor
from app.services.external_price_api import get_external_price_service

from pydantic import BaseModel, HttpUrl

router = APIRouter(prefix="/listings", tags=["FlashTrade"])
logger = logging.getLogger(__name__)


class AnalyzeRequest(BaseModel):
    image_url: str
    description: Optional[str] = None


@router.post("/analyze", status_code=status.HTTP_200_OK)
async def analyze_listing_image(
    request: AnalyzeRequest,
    current_user: User = Depends(get_current_active_user),
):
    """Analyze an image to get AI classification and valuation before creating listing"""
    ai_service = get_ai_service()
    try:
        ai_result = await ai_service.classify_ewaste(
            image_url=request.image_url, user_description=request.description
        )
        # Convert to dict and ensure Decimal fields are serialized as float
        result_dict = ai_result.model_dump()
        result_dict['estimated_value_min'] = float(result_dict['estimated_value_min'])
        result_dict['estimated_value_max'] = float(result_dict['estimated_value_max'])
        return result_dict
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI analysis failed: {str(e)}",
        )


@router.post("", response_model=ListingResponse, status_code=status.HTTP_201_CREATED)
async def create_listing(
    listing_data: ListingCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Create a new e-waste listing with AI-powered valuation (available to all user types)"""
    logger.info(f"Creating listing for user: {current_user.email} (type: {current_user.user_type.value})")

    # Call AI service to estimate value from the first image
    ai_service = get_ai_service()
    base_price = None

    try:
        # Use the first image for AI classification
        first_image_url = (
            listing_data.image_urls[0] if listing_data.image_urls else None
        )

        if first_image_url:
            # Get AI classification and valuation
            ai_result = await ai_service.classify_ewaste(
                image_url=first_image_url, user_description=listing_data.description
            )

            # Use AI-estimated values
            estimated_min = float(ai_result.estimated_value_min)
            estimated_max = float(ai_result.estimated_value_max)

            # Store AI classification data
            ai_classification = {
                "device_type": ai_result.device_type.value,
                "device_name": ai_result.device_name,
                "condition": ai_result.condition.value,
                "confidence_score": ai_result.confidence_score,
                "identified_components": ai_result.identified_components,
                "condition_notes": ai_result.condition_notes,
                "recycling_value_notes": ai_result.recycling_value_notes,
            }
        else:
            # Fallback if no image provided
            estimated_min = 1000.0
            estimated_max = 1500.0
            ai_classification = None

    except Exception as e:
        # Fallback to default values if AI service fails
        logger.warning(f"AI valuation failed: {e}")
        estimated_min = 1000.0
        estimated_max = 1500.0
        ai_classification = {"error": str(e)}

    # Use external trained model API for price prediction if user provided required fields
    if all([
        listing_data.brand,
        listing_data.build_quality is not None,
        listing_data.original_price is not None,
        listing_data.usage_pattern,
        listing_data.used_duration is not None,
        listing_data.user_lifespan is not None,
        listing_data.expiry_years is not None,
    ]):
        # Map device condition to numeric value (1-10 scale)
        condition_mapping = {
            DeviceCondition.NOT_WORKING: 3,
            DeviceCondition.PARTIALLY_WORKING: 6,
            DeviceCondition.WORKING: 9,
        }
        condition_numeric = condition_mapping.get(listing_data.condition, 7)

        # Map device type to product type string (capitalized for API)
        product_type_mapping = {
            "laptop": "Laptop",
            "desktop": "Desktop",
            "monitor": "Monitor",
            "mobile": "Mobile",
            "tablet": "Tablet",
            "other": "Other",
        }
        product_type = product_type_mapping.get(
            listing_data.device_type.value, "Other"
        )

        # Try external API first
        try:
            logger.info("Attempting price prediction with external API")
            external_service = get_external_price_service()
            base_price = await external_service.predict_price(
                brand=listing_data.brand,
                build_quality=listing_data.build_quality,
                condition=condition_numeric,
                expiry_years=listing_data.expiry_years,
                original_price=float(listing_data.original_price),
                product_type=product_type,
                usage_pattern=listing_data.usage_pattern,
                used_duration=listing_data.used_duration,
                user_lifespan=listing_data.user_lifespan
            )

            if base_price is not None:
                logger.info(f"External API price prediction successful: base_price = {base_price}")
            else:
                logger.warning("External API returned None, falling back to local model")

        except Exception as e:
            logger.error(f"External API price prediction failed: {e}, falling back to local model")
            base_price = None

        # Fallback to local ML model if external API failed
        if base_price is None:
            try:
                logger.info("Using local ML model as fallback")
                # Prepare input data for local ML model
                input_df = pd.DataFrame([{
                    'Brand': listing_data.brand,
                    'Product_Type': product_type,
                    'Build_Quality': listing_data.build_quality,
                    'Condition': condition_numeric,
                    'Original_Price': float(listing_data.original_price),
                    'Usage_Pattern': listing_data.usage_pattern,
                    'Used_Duration': listing_data.used_duration,
                    'User_Lifespan': listing_data.user_lifespan,
                    'Expiry_Years': listing_data.expiry_years,
                }])

                # Get local ML predictor and predict
                predictor = get_predictor()
                predictions = predictor.predict(input_df)

                if predictions and len(predictions) > 0:
                    base_price = Decimal(str(predictions[0]))
                    logger.info(f"Local ML price prediction successful: base_price = {base_price}")
                else:
                    logger.warning("Local ML prediction returned empty result")

            except Exception as e:
                logger.error(f"Local ML price prediction also failed: {e}")
                # Continue without base_price

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
        base_price=base_price,
        ai_classification=ai_classification,
    )

    session.add(listing)
    await session.commit()
    await session.refresh(listing)

    # Eagerly load relationships before returning
    await session.refresh(listing, ["seller", "buyer"])

    return listing


@router.get("/my", response_model=ListingList)
async def list_my_listings(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    status_filter: Optional[ListingStatus] = None,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """List current user's e-waste listings"""
    query = select(Listing).options(
        selectinload(Listing.seller), selectinload(Listing.buyer)
    ).where(Listing.seller_id == current_user.id)

    if status_filter:
        query = query.where(Listing.status == status_filter)

    # Get total count
    count_query = select(func.count()).select_from(Listing).where(Listing.seller_id == current_user.id)
    if status_filter:
        count_query = count_query.where(Listing.status == status_filter)

    total_result = await session.execute(count_query)
    total = total_result.scalar()

    # Get listings
    query = query.offset(skip).limit(limit).order_by(Listing.created_at.desc())
    result = await session.execute(query)
    listings = result.scalars().all()

    return ListingList(items=listings, total=total, skip=skip, limit=limit)


@router.get("", response_model=ListingList)
async def list_listings(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    status_filter: Optional[ListingStatus] = None,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """List all e-waste listings"""
    query = select(Listing).options(
        selectinload(Listing.seller), selectinload(Listing.buyer)
    )

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
    result = await session.execute(
        select(Listing)
        .options(selectinload(Listing.seller), selectinload(Listing.buyer))
        .where(Listing.id == listing_id)
    )
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
    result = await session.execute(
        select(Listing)
        .options(selectinload(Listing.seller), selectinload(Listing.buyer))
        .where(Listing.id == listing_id)
    )
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
