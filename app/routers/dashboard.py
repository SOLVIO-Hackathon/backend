from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from geoalchemy2.functions import ST_X, ST_Y

from app.core.database import get_async_session
from app.core.auth import require_admin, get_current_active_user
from app.models.user import User, UserType
from app.models.quest import Quest, QuestStatus
from app.models.listing import Listing, ListingStatus
from app.models.transaction import Transaction, PaymentStatus
from app.models.badge import Badge
from app.schemas.dashboard import (
    AnalyticsOverview, HeatmapPoint, LeaderboardEntry, DashboardResponse,
    WardStats, EWasteAnalytics, LiveUpdate
)

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

    # Calculate total transaction value from completed transactions
    total_value_result = await session.execute(
        select(func.coalesce(func.sum(Transaction.amount), 0))
        .where(Transaction.payment_status == PaymentStatus.COMPLETED)
    )
    total_transactions_value = float(total_value_result.scalar() or 0)

    # Calculate total waste collected from completed listings (in kg)
    waste_collected_result = await session.execute(
        select(func.coalesce(func.sum(Listing.weight_kg), 0))
        .where(Listing.status == ListingStatus.COMPLETED)
        .where(Listing.weight_kg.isnot(None))
    )
    total_waste_collected_kg = float(waste_collected_result.scalar() or 0)

    return AnalyticsOverview(
        total_users=total_users or 0,
        total_collectors=total_collectors or 0,
        total_kabadiwalas=total_kabadiwalas or 0,
        total_quests=total_quests or 0,
        quests_completed=quests_completed or 0,
        quests_pending=quests_pending or 0,
        total_listings=total_listings or 0,
        listings_active=listings_active or 0,
        total_transactions_value=total_transactions_value,
        total_waste_collected_kg=total_waste_collected_kg,
    )


@router.get("/heatmap", response_model=List[HeatmapPoint])
async def get_heatmap(
    status_filter: Optional[QuestStatus] = None,
    waste_type: Optional[str] = None,
    limit: int = Query(500, ge=1, le=1000),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Get heatmap data for quests with GPS coordinates"""
    # Build query with PostGIS ST_X and ST_Y to extract coordinates
    query = select(
        Quest.id,
        ST_X(Quest.location).label('longitude'),
        ST_Y(Quest.location).label('latitude'),
        Quest.waste_type,
        Quest.severity,
        Quest.status,
        Quest.created_at
    )
    
    # Apply filters
    if status_filter:
        query = query.where(Quest.status == status_filter)
    if waste_type:
        query = query.where(Quest.waste_type == waste_type)
    
    query = query.order_by(Quest.created_at.desc()).limit(limit)
    
    result = await session.execute(query)
    rows = result.all()

    heatmap_points = []
    for row in rows:
        heatmap_points.append(
            HeatmapPoint(
                id=str(row.id),
                latitude=row.latitude,
                longitude=row.longitude,
                waste_type=row.waste_type,
                severity=row.severity,
                status=row.status,
                created_at=row.created_at,
            )
        )

    return heatmap_points


@router.get("/leaderboard", response_model=List[LeaderboardEntry])
async def get_leaderboard(
    limit: int = Query(10, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Get top collectors leaderboard with actual calculations"""
    # Get collectors with aggregated data
    # Using subqueries for better performance
    
    # Subquery for completed quests count per collector
    completed_quests_subq = (
        select(
            Quest.collector_id,
            func.count(Quest.id).label('quests_completed')
        )
        .where(Quest.status == QuestStatus.VERIFIED)
        .group_by(Quest.collector_id)
        .subquery()
    )
    
    # Subquery for total bounty earned per collector
    bounty_subq = (
        select(
            Quest.collector_id,
            func.coalesce(func.sum(Quest.bounty_points), 0).label('total_bounty')
        )
        .where(Quest.status == QuestStatus.VERIFIED)
        .group_by(Quest.collector_id)
        .subquery()
    )
    
    # Subquery for badges count per user
    badges_subq = (
        select(
            Badge.user_id,
            func.count(Badge.id).label('badges_count')
        )
        .group_by(Badge.user_id)
        .subquery()
    )
    
    # Main query joining all data
    query = (
        select(
            User,
            func.coalesce(completed_quests_subq.c.quests_completed, 0).label('quests_completed'),
            func.coalesce(bounty_subq.c.total_bounty, 0).label('total_bounty'),
            func.coalesce(badges_subq.c.badges_count, 0).label('badges_count')
        )
        .outerjoin(completed_quests_subq, User.id == completed_quests_subq.c.collector_id)
        .outerjoin(bounty_subq, User.id == bounty_subq.c.collector_id)
        .outerjoin(badges_subq, User.id == badges_subq.c.user_id)
        .where(User.user_type == UserType.COLLECTOR)
        .order_by(
            func.coalesce(completed_quests_subq.c.quests_completed, 0).desc(),
            User.reputation_score.desc()
        )
        .limit(limit)
    )
    
    result = await session.execute(query)
    rows = result.all()

    leaderboard = []
    for idx, row in enumerate(rows, 1):
        collector = row[0]
        leaderboard.append(
            LeaderboardEntry(
                rank=idx,
                user={
                    "id": collector.id,
                    "full_name": collector.full_name,
                    "user_type": collector.user_type,
                    "reputation_score": collector.reputation_score,
                },
                quests_completed=row.quests_completed,
                total_bounty_earned=float(row.total_bounty),
                badges_count=row.badges_count,
            )
        )

    return leaderboard


@router.get("/ward-stats", response_model=List[WardStats])
async def get_ward_stats(
    geohash_prefix: Optional[str] = Query(None, description="Filter by geohash prefix for ward-level filtering"),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Get ward-level statistics aggregated by geohash prefix"""
    # Group quests by geohash prefix (first 5 chars for ward-level)
    # This provides approximate ward-level grouping
    geohash_length = 5  # Approximately covers a small area like a ward
    
    query = select(
        func.substr(Quest.geohash, 1, geohash_length).label('ward_geohash'),
        func.count(Quest.id).label('total_quests'),
        func.count(Quest.id).filter(Quest.status == QuestStatus.VERIFIED).label('completed_quests'),
        func.count(Quest.id).filter(Quest.status.in_([QuestStatus.REPORTED, QuestStatus.ASSIGNED])).label('pending_quests'),
    ).group_by(func.substr(Quest.geohash, 1, geohash_length))
    
    # Apply geohash prefix filter if provided
    if geohash_prefix:
        query = query.where(Quest.geohash.startswith(geohash_prefix))
    
    result = await session.execute(query)
    rows = result.all()
    
    ward_stats = []
    for row in rows:
        ward_stats.append(
            WardStats(
                ward_name=f"Area {row.ward_geohash}",
                geohash_prefix=row.ward_geohash,
                total_quests=row.total_quests,
                completed_quests=row.completed_quests,
                pending_quests=row.pending_quests,
                total_waste_kg=0.0,  # Will be calculated from listings
            )
        )
    
    return ward_stats


@router.get("/ewaste-analytics", response_model=EWasteAnalytics)
async def get_ewaste_analytics(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Get e-waste analytics including device listings and material value estimates"""
    # Total listings count
    total_listings_result = await session.execute(select(func.count()).select_from(Listing))
    total_listings = total_listings_result.scalar() or 0
    
    # Active listings count
    active_listings_result = await session.execute(
        select(func.count()).select_from(Listing)
        .where(Listing.status.in_([ListingStatus.LISTED, ListingStatus.BIDDING]))
    )
    active_listings = active_listings_result.scalar() or 0
    
    # Completed listings count
    completed_listings_result = await session.execute(
        select(func.count()).select_from(Listing)
        .where(Listing.status == ListingStatus.COMPLETED)
    )
    completed_listings = completed_listings_result.scalar() or 0
    
    # Device type breakdown
    device_breakdown_result = await session.execute(
        select(
            Listing.device_type,
            func.count(Listing.id).label('count')
        )
        .where(Listing.device_type.isnot(None))
        .group_by(Listing.device_type)
    )
    device_breakdown = {str(row.device_type.value): row.count for row in device_breakdown_result.all()}
    
    # Total estimated value (sum of min and max averages)
    value_result = await session.execute(
        select(
            func.coalesce(func.sum(Listing.estimated_value_min), 0).label('min_value'),
            func.coalesce(func.sum(Listing.estimated_value_max), 0).label('max_value'),
            func.coalesce(func.sum(Listing.final_price), 0).label('total_realized')
        )
    )
    value_row = value_result.one()
    
    # Average value per listing
    avg_value_result = await session.execute(
        select(
            func.coalesce(func.avg((Listing.estimated_value_min + Listing.estimated_value_max) / 2), 0)
        )
    )
    avg_value = float(avg_value_result.scalar() or 0)
    
    # Recent listings (last 10)
    recent_listings_result = await session.execute(
        select(Listing)
        .order_by(Listing.created_at.desc())
        .limit(10)
    )
    recent_listings = [
        {
            "id": str(listing.id),
            "device_type": listing.device_type.value,
            "device_name": listing.device_name,
            "condition": listing.condition.value,
            "estimated_value_min": float(listing.estimated_value_min),
            "estimated_value_max": float(listing.estimated_value_max),
            "status": listing.status.value,
            "created_at": listing.created_at.isoformat(),
        }
        for listing in recent_listings_result.scalars().all()
    ]
    
    return EWasteAnalytics(
        total_listings=total_listings,
        active_listings=active_listings,
        completed_listings=completed_listings,
        device_type_breakdown=device_breakdown,
        total_estimated_value_min=float(value_row.min_value),
        total_estimated_value_max=float(value_row.max_value),
        total_realized_value=float(value_row.total_realized),
        average_listing_value=avg_value,
        recent_listings=recent_listings,
    )


@router.get("/live-updates", response_model=LiveUpdate)
async def get_live_updates(
    since_timestamp: Optional[str] = Query(None, description="ISO timestamp to get updates since"),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Get live/real-time updates for dashboard (HTTP polling endpoint)"""
    # Parse since_timestamp or default to last 5 minutes
    since = None
    if since_timestamp:
        try:
            # Handle various timezone formats
            ts = since_timestamp.replace('Z', '+00:00')
            # Remove any existing timezone info for naive datetime
            if '+' in ts:
                ts = ts.split('+')[0]
            elif ts.endswith('Z'):
                ts = ts[:-1]
            since = datetime.fromisoformat(ts)
        except (ValueError, TypeError):
            since = None
    
    if since is None:
        since = datetime.utcnow() - timedelta(minutes=5)
    
    # Get recent quests
    recent_quests_result = await session.execute(
        select(
            Quest.id,
            Quest.title,
            Quest.status,
            Quest.waste_type,
            Quest.created_at,
            Quest.updated_at
        )
        .where(Quest.updated_at > since)
        .order_by(Quest.updated_at.desc())
        .limit(20)
    )
    recent_quests = [
        {
            "id": str(row.id),
            "title": row.title,
            "status": row.status.value,
            "waste_type": row.waste_type.value,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }
        for row in recent_quests_result.all()
    ]
    
    # Get recent listings
    recent_listings_result = await session.execute(
        select(
            Listing.id,
            Listing.device_name,
            Listing.status,
            Listing.device_type,
            Listing.created_at,
            Listing.updated_at
        )
        .where(Listing.updated_at > since)
        .order_by(Listing.updated_at.desc())
        .limit(20)
    )
    recent_listings = [
        {
            "id": str(row.id),
            "device_name": row.device_name,
            "status": row.status.value,
            "device_type": row.device_type.value,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }
        for row in recent_listings_result.all()
    ]
    
    # Get activity counts
    new_quests_count = await session.execute(
        select(func.count()).select_from(Quest).where(Quest.created_at > since)
    )
    new_listings_count = await session.execute(
        select(func.count()).select_from(Listing).where(Listing.created_at > since)
    )
    
    return LiveUpdate(
        timestamp=datetime.utcnow().isoformat(),
        recent_quests=recent_quests,
        recent_listings=recent_listings,
        new_quests_count=new_quests_count.scalar() or 0,
        new_listings_count=new_listings_count.scalar() or 0,
    )
