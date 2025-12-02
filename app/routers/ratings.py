"""Rating and review endpoints for kabadiwala performance"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.core.database import get_async_session
from app.core.auth import get_current_active_user
from app.models.user import User, UserType
from app.models.listing import Listing, ListingStatus
from app.models.rating import Rating
from pydantic import BaseModel, Field

router = APIRouter(prefix="/ratings", tags=["Reputation & Ratings"])


# Schemas
class RatingCreate(BaseModel):
    """Create a rating for a kabadiwala"""
    listing_id: UUID = Field(description="The listing ID for this transaction")
    rating: int = Field(ge=1, le=5, description="Overall rating (1-5 stars)")
    review: Optional[str] = Field(None, max_length=1000, description="Optional review text")
    punctuality_rating: Optional[int] = Field(None, ge=1, le=5, description="Punctuality rating (1-5)")
    professionalism_rating: Optional[int] = Field(None, ge=1, le=5, description="Professionalism rating (1-5)")
    communication_rating: Optional[int] = Field(None, ge=1, le=5, description="Communication rating (1-5)")


class RatingResponse(BaseModel):
    """Rating response schema"""
    id: UUID
    seller_id: UUID
    kabadiwala_id: UUID
    listing_id: UUID
    rating: int
    review: Optional[str]
    punctuality_rating: Optional[int]
    professionalism_rating: Optional[int]
    communication_rating: Optional[int]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class RatingWithSellerInfo(BaseModel):
    """Rating with seller information"""
    id: UUID
    seller_id: UUID
    seller_name: str
    kabadiwala_id: UUID
    listing_id: UUID
    rating: int
    review: Optional[str]
    punctuality_rating: Optional[int]
    professionalism_rating: Optional[int]
    communication_rating: Optional[int]
    created_at: str


class KabadiwalaRatingSummary(BaseModel):
    """Summary of kabadiwala ratings"""
    kabadiwala_id: UUID
    kabadiwala_name: str
    average_rating: float
    total_ratings: int
    average_punctuality: Optional[float]
    average_professionalism: Optional[float]
    average_communication: Optional[float]
    rating_distribution: dict  # {"5": 10, "4": 5, "3": 2, "2": 0, "1": 0}
    recent_reviews: List[RatingWithSellerInfo]


@router.post("", response_model=RatingResponse, status_code=status.HTTP_201_CREATED)
async def create_rating(
    rating_data: RatingCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Create a rating for a kabadiwala after a successful transaction.
    Only the seller can rate the kabadiwala who picked up their item.
    """
    # Get listing
    listing_result = await session.execute(
        select(Listing).where(Listing.id == rating_data.listing_id)
    )
    listing = listing_result.scalar_one_or_none()

    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found"
        )

    # Verify current user is the seller
    if listing.seller_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the seller can rate the kabadiwala"
        )

    # Verify listing has a buyer (kabadiwala)
    if not listing.buyer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This listing has no assigned kabadiwala to rate"
        )

    # Verify listing is picked up or completed
    if listing.status not in [ListingStatus.PICKED_UP, ListingStatus.COMPLETED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only rate after pickup is completed"
        )

    # Check if rating already exists
    existing_rating = await session.execute(
        select(Rating).where(
            and_(
                Rating.listing_id == rating_data.listing_id,
                Rating.seller_id == current_user.id
            )
        )
    )
    if existing_rating.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already rated this transaction"
        )

    # Create rating
    new_rating = Rating(
        seller_id=current_user.id,
        kabadiwala_id=listing.buyer_id,
        listing_id=rating_data.listing_id,
        rating=rating_data.rating,
        review=rating_data.review,
        punctuality_rating=rating_data.punctuality_rating,
        professionalism_rating=rating_data.professionalism_rating,
        communication_rating=rating_data.communication_rating,
    )

    session.add(new_rating)

    # Update kabadiwala reputation score
    kabadiwala_result = await session.execute(
        select(User).where(User.id == listing.buyer_id)
    )
    kabadiwala = kabadiwala_result.scalar_one_or_none()

    if kabadiwala:
        # Recalculate average rating
        avg_rating_result = await session.execute(
            select(func.avg(Rating.rating))
            .where(Rating.kabadiwala_id == listing.buyer_id)
        )
        avg_rating = avg_rating_result.scalar()

        # Update reputation score to average rating
        if avg_rating:
            kabadiwala.reputation_score = float(avg_rating)

    await session.commit()
    await session.refresh(new_rating)

    return RatingResponse(
        id=new_rating.id,
        seller_id=new_rating.seller_id,
        kabadiwala_id=new_rating.kabadiwala_id,
        listing_id=new_rating.listing_id,
        rating=new_rating.rating,
        review=new_rating.review,
        punctuality_rating=new_rating.punctuality_rating,
        professionalism_rating=new_rating.professionalism_rating,
        communication_rating=new_rating.communication_rating,
        created_at=new_rating.created_at.isoformat(),
        updated_at=new_rating.updated_at.isoformat()
    )


@router.get("/kabadiwala/{kabadiwala_id}", response_model=KabadiwalaRatingSummary)
async def get_kabadiwala_ratings(
    kabadiwala_id: UUID,
    limit: int = Query(10, ge=1, le=50, description="Number of recent reviews to return"),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get rating summary and reviews for a specific kabadiwala.
    Includes average ratings, distribution, and recent reviews.
    """
    # Verify kabadiwala exists
    kabadiwala_result = await session.execute(
        select(User).where(User.id == kabadiwala_id)
    )
    kabadiwala = kabadiwala_result.scalar_one_or_none()

    if not kabadiwala:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kabadiwala not found"
        )

    if kabadiwala.user_type != UserType.KABADIWALA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not a kabadiwala"
        )

    # Get all ratings for this kabadiwala
    ratings_result = await session.execute(
        select(Rating)
        .where(Rating.kabadiwala_id == kabadiwala_id)
        .order_by(Rating.created_at.desc())
    )
    all_ratings = ratings_result.scalars().all()

    if not all_ratings:
        return KabadiwalaRatingSummary(
            kabadiwala_id=kabadiwala_id,
            kabadiwala_name=kabadiwala.full_name,
            average_rating=0.0,
            total_ratings=0,
            average_punctuality=None,
            average_professionalism=None,
            average_communication=None,
            rating_distribution={"5": 0, "4": 0, "3": 0, "2": 0, "1": 0},
            recent_reviews=[]
        )

    # Calculate statistics
    total_ratings = len(all_ratings)
    average_rating = sum(r.rating for r in all_ratings) / total_ratings

    # Calculate optional criteria averages
    punctuality_ratings = [r.punctuality_rating for r in all_ratings if r.punctuality_rating is not None]
    professionalism_ratings = [r.professionalism_rating for r in all_ratings if r.professionalism_rating is not None]
    communication_ratings = [r.communication_rating for r in all_ratings if r.communication_rating is not None]

    average_punctuality = sum(punctuality_ratings) / len(punctuality_ratings) if punctuality_ratings else None
    average_professionalism = sum(professionalism_ratings) / len(professionalism_ratings) if professionalism_ratings else None
    average_communication = sum(communication_ratings) / len(communication_ratings) if communication_ratings else None

    # Calculate rating distribution
    rating_distribution = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
    for rating in all_ratings:
        rating_distribution[str(rating.rating)] += 1

    # Get recent reviews with seller info
    recent_ratings = all_ratings[:limit]
    recent_reviews = []

    for rating in recent_ratings:
        seller_result = await session.execute(
            select(User).where(User.id == rating.seller_id)
        )
        seller = seller_result.scalar_one_or_none()

        recent_reviews.append(
            RatingWithSellerInfo(
                id=rating.id,
                seller_id=rating.seller_id,
                seller_name=seller.full_name if seller else "Unknown",
                kabadiwala_id=rating.kabadiwala_id,
                listing_id=rating.listing_id,
                rating=rating.rating,
                review=rating.review,
                punctuality_rating=rating.punctuality_rating,
                professionalism_rating=rating.professionalism_rating,
                communication_rating=rating.communication_rating,
                created_at=rating.created_at.isoformat()
            )
        )

    return KabadiwalaRatingSummary(
        kabadiwala_id=kabadiwala_id,
        kabadiwala_name=kabadiwala.full_name,
        average_rating=round(average_rating, 2),
        total_ratings=total_ratings,
        average_punctuality=round(average_punctuality, 2) if average_punctuality else None,
        average_professionalism=round(average_professionalism, 2) if average_professionalism else None,
        average_communication=round(average_communication, 2) if average_communication else None,
        rating_distribution=rating_distribution,
        recent_reviews=recent_reviews
    )


@router.get("/my-ratings", response_model=List[RatingResponse])
async def get_my_ratings_as_kabadiwala(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get all ratings received by the current user (must be kabadiwala).
    """
    if current_user.user_type != UserType.KABADIWALA:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only kabadiwalas can view their received ratings"
        )

    ratings_result = await session.execute(
        select(Rating)
        .where(Rating.kabadiwala_id == current_user.id)
        .order_by(Rating.created_at.desc())
    )
    ratings = ratings_result.scalars().all()

    return [
        RatingResponse(
            id=rating.id,
            seller_id=rating.seller_id,
            kabadiwala_id=rating.kabadiwala_id,
            listing_id=rating.listing_id,
            rating=rating.rating,
            review=rating.review,
            punctuality_rating=rating.punctuality_rating,
            professionalism_rating=rating.professionalism_rating,
            communication_rating=rating.communication_rating,
            created_at=rating.created_at.isoformat(),
            updated_at=rating.updated_at.isoformat()
        )
        for rating in ratings
    ]


@router.get("/listing/{listing_id}", response_model=RatingResponse)
async def get_rating_for_listing(
    listing_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get the rating for a specific listing (if it exists).
    """
    rating_result = await session.execute(
        select(Rating).where(Rating.listing_id == listing_id)
    )
    rating = rating_result.scalar_one_or_none()

    if not rating:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No rating found for this listing"
        )

    # Verify user has access (seller or kabadiwala involved)
    if rating.seller_id != current_user.id and rating.kabadiwala_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this rating"
        )

    return RatingResponse(
        id=rating.id,
        seller_id=rating.seller_id,
        kabadiwala_id=rating.kabadiwala_id,
        listing_id=rating.listing_id,
        rating=rating.rating,
        review=rating.review,
        punctuality_rating=rating.punctuality_rating,
        professionalism_rating=rating.professionalism_rating,
        communication_rating=rating.communication_rating,
        created_at=rating.created_at.isoformat(),
        updated_at=rating.updated_at.isoformat()
    )


@router.get("/top-kabadiwalas", response_model=List[dict])
async def get_top_rated_kabadiwalas(
    limit: int = Query(10, ge=1, le=50, description="Number of top kabadiwalas to return"),
    min_ratings: int = Query(5, ge=1, description="Minimum number of ratings required"),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get top-rated kabadiwalas based on average rating.
    Only includes kabadiwalas with minimum number of ratings.
    """
    # Get all kabadiwalas with ratings
    kabadiwalas_result = await session.execute(
        select(User).where(User.user_type == UserType.KABADIWALA)
    )
    kabadiwalas = kabadiwalas_result.scalars().all()

    top_kabadiwalas = []

    for kabadiwala in kabadiwalas:
        # Get rating stats
        ratings_result = await session.execute(
            select(Rating).where(Rating.kabadiwala_id == kabadiwala.id)
        )
        ratings = ratings_result.scalars().all()

        if len(ratings) >= min_ratings:
            avg_rating = sum(r.rating for r in ratings) / len(ratings)
            top_kabadiwalas.append({
                "kabadiwala_id": kabadiwala.id,
                "name": kabadiwala.full_name,
                "average_rating": round(avg_rating, 2),
                "total_ratings": len(ratings),
                "reputation_score": kabadiwala.reputation_score,
                "total_transactions": kabadiwala.total_transactions
            })

    # Sort by average rating descending
    top_kabadiwalas.sort(key=lambda x: x["average_rating"], reverse=True)

    return top_kabadiwalas[:limit]
