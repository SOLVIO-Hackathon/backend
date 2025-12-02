"""Badge and reputation management endpoints"""

from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.core.database import get_async_session
from app.core.auth import get_current_active_user
from app.models.user import User, UserType
from app.models.badge import Badge, BadgeType
from app.models.listing import Listing, ListingStatus
from app.models.quest import Quest, QuestStatus
from pydantic import BaseModel, Field

router = APIRouter(prefix="/badges", tags=["Reputation & Badges"])


# Schemas
class BadgeResponse(BaseModel):
    """Badge response schema"""
    id: UUID
    user_id: UUID
    badge_type: BadgeType
    awarded_at: str

    class Config:
        from_attributes = True


class BadgeAwardResponse(BaseModel):
    """Response when badge is awarded"""
    badge: BadgeResponse
    message: str


class UserBadgesResponse(BaseModel):
    """User's badges summary"""
    user_id: UUID
    full_name: str
    user_type: UserType
    reputation_score: float
    total_transactions: int
    badges: List[BadgeResponse]


# Badge criteria
BADGE_CRITERIA = {
    BadgeType.E_WASTE_PRO: {
        "description": "Complete 10 e-waste listings",
        "check": lambda user_id, session: check_ewaste_listings(user_id, session, min_count=10)
    },
    BadgeType.ORGANIC_HERO: {
        "description": "Complete 20 organic waste quests",
        "check": lambda user_id, session: check_quest_type(user_id, session, waste_type="organic", min_count=20)
    },
    BadgeType.TOP_COLLECTOR: {
        "description": "Complete 50 total quests",
        "check": lambda user_id, session: check_total_quests(user_id, session, min_count=50)
    },
    BadgeType.TRUSTED_KABADIWALA: {
        "description": "Complete 25 successful pickups with 4.5+ rating",
        "check": lambda user_id, session: check_kabadiwala_performance(user_id, session, min_pickups=25, min_rating=4.5)
    },
    BadgeType.RECYCLING_CHAMPION: {
        "description": "Achieve 1000+ reputation score",
        "check": lambda user_id, session: check_reputation_score(user_id, session, min_score=1000)
    },
    BadgeType.VERIFIED_SELLER: {
        "description": "Complete 5 verified e-waste sales",
        "check": lambda user_id, session: check_verified_sales(user_id, session, min_count=5)
    },
}


# Helper functions to check badge criteria
async def check_ewaste_listings(user_id: UUID, session: AsyncSession, min_count: int) -> bool:
    """Check if user has completed enough e-waste listings"""
    result = await session.execute(
        select(func.count(Listing.id))
        .where(
            and_(
                Listing.seller_id == user_id,
                Listing.status == ListingStatus.COMPLETED
            )
        )
    )
    count = result.scalar()
    return count >= min_count


async def check_quest_type(user_id: UUID, session: AsyncSession, waste_type: str, min_count: int) -> bool:
    """Check if user completed enough quests of specific type"""
    result = await session.execute(
        select(func.count(Quest.id))
        .where(
            and_(
                Quest.collector_id == user_id,
                Quest.status == QuestStatus.COMPLETED,
                Quest.waste_type == waste_type
            )
        )
    )
    count = result.scalar()
    return count >= min_count


async def check_total_quests(user_id: UUID, session: AsyncSession, min_count: int) -> bool:
    """Check total completed quests"""
    result = await session.execute(
        select(func.count(Quest.id))
        .where(
            and_(
                Quest.collector_id == user_id,
                Quest.status == QuestStatus.COMPLETED
            )
        )
    )
    count = result.scalar()
    return count >= min_count


async def check_kabadiwala_performance(user_id: UUID, session: AsyncSession, min_pickups: int, min_rating: float) -> bool:
    """Check kabadiwala performance metrics"""
    # Get user
    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()

    if not user or user.user_type != UserType.KABADIWALA:
        return False

    # Check completed pickups
    result = await session.execute(
        select(func.count(Listing.id))
        .where(
            and_(
                Listing.buyer_id == user_id,
                Listing.status.in_([ListingStatus.PICKED_UP, ListingStatus.COMPLETED])
            )
        )
    )
    pickup_count = result.scalar()

    # Check reputation score (used as rating proxy)
    return pickup_count >= min_pickups and user.reputation_score >= min_rating


async def check_reputation_score(user_id: UUID, session: AsyncSession, min_score: float) -> bool:
    """Check if user has minimum reputation score"""
    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()

    if not user:
        return False

    return user.reputation_score >= min_score


async def check_verified_sales(user_id: UUID, session: AsyncSession, min_count: int) -> bool:
    """Check verified e-waste sales"""
    result = await session.execute(
        select(func.count(Listing.id))
        .where(
            and_(
                Listing.seller_id == user_id,
                Listing.status == ListingStatus.COMPLETED,
                Listing.weight_verified == True
            )
        )
    )
    count = result.scalar()
    return count >= min_count


async def check_user_has_badge(user_id: UUID, badge_type: BadgeType, session: AsyncSession) -> bool:
    """Check if user already has a specific badge"""
    result = await session.execute(
        select(func.count(Badge.id))
        .where(
            and_(
                Badge.user_id == user_id,
                Badge.badge_type == badge_type
            )
        )
    )
    count = result.scalar()
    return count > 0


# Endpoints
@router.get("/user/{user_id}", response_model=UserBadgesResponse)
async def get_user_badges(
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Get all badges for a specific user"""
    # Get user
    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Get badges
    badges_result = await session.execute(
        select(Badge).where(Badge.user_id == user_id).order_by(Badge.awarded_at.desc())
    )
    badges = badges_result.scalars().all()

    return UserBadgesResponse(
        user_id=user.id,
        full_name=user.full_name,
        user_type=user.user_type,
        reputation_score=user.reputation_score,
        total_transactions=user.total_transactions,
        badges=[
            BadgeResponse(
                id=badge.id,
                user_id=badge.user_id,
                badge_type=badge.badge_type,
                awarded_at=badge.awarded_at.isoformat()
            )
            for badge in badges
        ]
    )


@router.get("/my-badges", response_model=UserBadgesResponse)
async def get_my_badges(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Get current user's badges"""
    # Get badges
    badges_result = await session.execute(
        select(Badge).where(Badge.user_id == current_user.id).order_by(Badge.awarded_at.desc())
    )
    badges = badges_result.scalars().all()

    return UserBadgesResponse(
        user_id=current_user.id,
        full_name=current_user.full_name,
        user_type=current_user.user_type,
        reputation_score=current_user.reputation_score,
        total_transactions=current_user.total_transactions,
        badges=[
            BadgeResponse(
                id=badge.id,
                user_id=badge.user_id,
                badge_type=badge.badge_type,
                awarded_at=badge.awarded_at.isoformat()
            )
            for badge in badges
        ]
    )


@router.post("/check-and-award/{user_id}", response_model=List[BadgeAwardResponse])
async def check_and_award_badges(
    user_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Check if user qualifies for any new badges and award them automatically.
    This endpoint should be called after significant user actions (quest completion, listing completion, etc.)
    """
    # Verify user exists
    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Users can check their own badges, or admins can check anyone's
    if current_user.id != user_id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to award badges for this user"
        )

    awarded_badges = []

    # Check each badge type
    for badge_type, criteria in BADGE_CRITERIA.items():
        # Skip if user already has this badge
        if await check_user_has_badge(user_id, badge_type, session):
            continue

        # Check if user meets criteria
        try:
            if await criteria["check"](user_id, session):
                # Award badge
                new_badge = Badge(
                    user_id=user_id,
                    badge_type=badge_type
                )
                session.add(new_badge)
                await session.commit()
                await session.refresh(new_badge)

                awarded_badges.append(
                    BadgeAwardResponse(
                        badge=BadgeResponse(
                            id=new_badge.id,
                            user_id=new_badge.user_id,
                            badge_type=new_badge.badge_type,
                            awarded_at=new_badge.awarded_at.isoformat()
                        ),
                        message=f"Congratulations! You earned the {badge_type.value} badge: {criteria['description']}"
                    )
                )
        except Exception as e:
            # Log error but continue checking other badges
            print(f"Error checking badge {badge_type}: {e}")
            continue

    return awarded_badges


@router.post("/award-manual/{user_id}/{badge_type}", response_model=BadgeAwardResponse)
async def award_badge_manually(
    user_id: UUID,
    badge_type: BadgeType,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Manually award a badge to a user (admin only).
    Useful for special achievements or promotional badges.
    """
    # Only admins can manually award badges
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can manually award badges"
        )

    # Verify user exists
    user_result = await session.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Check if user already has this badge
    if await check_user_has_badge(user_id, badge_type, session):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has this badge"
        )

    # Award badge
    new_badge = Badge(
        user_id=user_id,
        badge_type=badge_type
    )
    session.add(new_badge)
    await session.commit()
    await session.refresh(new_badge)

    return BadgeAwardResponse(
        badge=BadgeResponse(
            id=new_badge.id,
            user_id=new_badge.user_id,
            badge_type=new_badge.badge_type,
            awarded_at=new_badge.awarded_at.isoformat()
        ),
        message=f"Badge {badge_type.value} manually awarded to {user.full_name}"
    )


@router.get("/criteria", response_model=dict)
async def get_badge_criteria(
    current_user: User = Depends(get_current_active_user),
):
    """Get badge criteria information for all badge types"""
    return {
        badge_type.value: {
            "description": criteria["description"],
            "type": badge_type.value
        }
        for badge_type, criteria in BADGE_CRITERIA.items()
    }
