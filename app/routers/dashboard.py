from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_async_session
from app.core.auth import require_admin
from app.models.user import User, UserType
from app.models.quest import Quest, QuestStatus
from app.models.listing import Listing, ListingStatus
from app.schemas.dashboard import AnalyticsOverview, HeatmapPoint, LeaderboardEntry, DashboardResponse

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/analytics", response_model=AnalyticsOverview)
async def get_analytics(
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """Get overall platform analytics (Admin only)"""
    # Count users
    total_users_result = await session.execute(select(func.count()).select_from(User))
    total_users = total_users_result.scalar()

    collectors_result = await session.execute(
        select(func.count()).select_from(User).where(User.user_type == UserType.COLLECTOR)
    )
    total_collectors = collectors_result.scalar()

    kabadiwalas_result = await session.execute(
        select(func.count()).select_from(User).where(User.user_type == UserType.KABADIWALA)
    )
    total_kabadiwalas = kabadiwalas_result.scalar()

    # Count quests
    total_quests_result = await session.execute(select(func.count()).select_from(Quest))
    total_quests = total_quests_result.scalar()

    completed_quests_result = await session.execute(
        select(func.count()).select_from(Quest).where(Quest.status == QuestStatus.VERIFIED)
    )
    quests_completed = completed_quests_result.scalar()

    pending_quests_result = await session.execute(
        select(func.count()).select_from(Quest).where(Quest.status.in_([QuestStatus.REPORTED, QuestStatus.ASSIGNED]))
    )
    quests_pending = pending_quests_result.scalar()

    # Count listings
    total_listings_result = await session.execute(select(func.count()).select_from(Listing))
    total_listings = total_listings_result.scalar()

    active_listings_result = await session.execute(
        select(func.count()).select_from(Listing).where(Listing.status.in_([ListingStatus.LISTED, ListingStatus.BIDDING]))
    )
    listings_active = active_listings_result.scalar()

    return AnalyticsOverview(
        total_users=total_users or 0,
        total_collectors=total_collectors or 0,
        total_kabadiwalas=total_kabadiwalas or 0,
        total_quests=total_quests or 0,
        quests_completed=quests_completed or 0,
        quests_pending=quests_pending or 0,
        total_listings=total_listings or 0,
        listings_active=listings_active or 0,
        total_transactions_value=0.0,  # TODO: Calculate from transactions
        total_waste_collected_kg=0.0,  # TODO: Calculate from completed quests
    )


@router.get("/heatmap", response_model=List[HeatmapPoint])
async def get_heatmap(
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """Get heatmap data for quests"""
    # Get all quests with location data
    result = await session.execute(
        select(Quest).order_by(Quest.created_at.desc()).limit(500)
    )
    quests = result.scalars().all()

    # TODO: Convert PostGIS POINT to lat/lng
    # For now, return empty list
    return []


@router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(
    limit: int = 10,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """Get top collectors leaderboard"""
    # TODO: Implement proper leaderboard query with aggregations
    result = await session.execute(
        select(User)
        .where(User.user_type == UserType.COLLECTOR)
        .order_by(User.reputation_score.desc())
        .limit(limit)
    )
    collectors = result.scalars().all()

    leaderboard = []
    for idx, collector in enumerate(collectors, 1):
        leaderboard.append(
            LeaderboardEntry(
                rank=idx,
                user={
                    "id": collector.id,
                    "full_name": collector.full_name,
                    "user_type": collector.user_type,
                    "reputation_score": collector.reputation_score,
                },
                quests_completed=0,  # TODO: Calculate from quests
                total_bounty_earned=0.0,  # TODO: Calculate from transactions
                badges_count=0,  # TODO: Count badges
            )
        )

    return leaderboard
