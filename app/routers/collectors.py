"""
Collector availability and workload management endpoints.
"""

from typing import Optional, List
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field

from app.core.database import get_async_session
from app.core.auth import get_current_active_user
from app.models.user import User, UserType
from app.models.quest import Quest, QuestStatus
from app.schemas.quest import QuestResponse, QuestList


router = APIRouter(prefix="/collectors", tags=["Collectors"])


# Pydantic schemas
class LocationUpdate(BaseModel):
    """Update collector location"""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class AvailabilityUpdate(BaseModel):
    """Update collector availability status"""
    status: str = Field(..., pattern="^(available|busy|offline)$")


class WorkloadResponse(BaseModel):
    """Collector workload information"""
    active_quests: int
    max_concurrent: int
    capacity_remaining: int
    completed_last_week: int
    status: str
    fraud_risk_score: float


@router.patch("/me/location", status_code=status.HTTP_200_OK)
async def update_collector_location(
    location: LocationUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Update collector's current location.
    
    This is used by the automatic assignment algorithm to find nearby collectors.
    """
    if current_user.user_type != UserType.COLLECTOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only collectors can update their location"
        )
    
    # Update location
    current_user.current_location_lat = location.latitude
    current_user.current_location_lng = location.longitude
    current_user.last_location_update = datetime.utcnow()
    
    await session.commit()
    await session.refresh(current_user)
    
    return {
        "message": "Location updated successfully",
        "latitude": current_user.current_location_lat,
        "longitude": current_user.current_location_lng,
        "last_updated": current_user.last_location_update
    }


@router.patch("/me/availability", status_code=status.HTTP_200_OK)
async def update_collector_availability(
    availability: AvailabilityUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Update collector's availability status.
    
    Statuses:
    - available: Ready to receive new quest assignments
    - busy: Currently occupied, won't receive new assignments
    - offline: Not accepting any new assignments
    """
    if current_user.user_type != UserType.COLLECTOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only collectors can update their availability"
        )
    
    current_user.collector_status = availability.status
    
    await session.commit()
    await session.refresh(current_user)
    
    return {
        "message": "Availability updated successfully",
        "status": current_user.collector_status
    }


@router.get("/me/workload", response_model=WorkloadResponse)
async def get_collector_workload(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get collector's current workload and fraud risk score.
    """
    if current_user.user_type != UserType.COLLECTOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only collectors can view their workload"
        )
    
    # Count active quests
    active_query = select(func.count(Quest.id)).where(
        Quest.collector_id == current_user.id,
        Quest.status.in_([QuestStatus.ASSIGNED, QuestStatus.IN_PROGRESS])
    )
    active_result = await session.execute(active_query)
    active_quests = active_result.scalar() or 0
    
    # Count completed quests in last 7 days
    from datetime import timedelta
    week_ago = datetime.utcnow() - timedelta(days=7)
    completed_query = select(func.count(Quest.id)).where(
        Quest.collector_id == current_user.id,
        Quest.status == QuestStatus.VERIFIED,
        Quest.verified_at >= week_ago
    )
    completed_result = await session.execute(completed_query)
    completed_last_week = completed_result.scalar() or 0
    
    return WorkloadResponse(
        active_quests=active_quests,
        max_concurrent=current_user.max_concurrent_quests,
        capacity_remaining=current_user.max_concurrent_quests - active_quests,
        completed_last_week=completed_last_week,
        status=current_user.collector_status or "available",
        fraud_risk_score=current_user.fraud_risk_score
    )


@router.get("/me/quests", response_model=QuestList)
async def get_my_assigned_quests(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    status_filter: Optional[QuestStatus] = None,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get all quests assigned to the current collector.

    Collectors can filter by status to view:
    - ASSIGNED: Newly assigned quests not yet started
    - IN_PROGRESS: Quests currently being worked on
    - COMPLETED: Quests completed and awaiting verification
    - VERIFIED: Successfully verified quests
    - REJECTED: Quests that were rejected

    Returns paginated list of quests with full details including reporter info.
    """
    if current_user.user_type != UserType.COLLECTOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only collectors can view assigned quests"
        )

    # Build query for quests assigned to this collector
    query = select(Quest).where(
        Quest.collector_id == current_user.id
    ).options(
        selectinload(Quest.reporter),
        selectinload(Quest.collector)
    )

    # Apply status filter if provided
    if status_filter:
        query = query.where(Quest.status == status_filter)

    # Get total count
    count_query = select(func.count()).select_from(Quest).where(
        Quest.collector_id == current_user.id
    )
    if status_filter:
        count_query = count_query.where(Quest.status == status_filter)

    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated quests, ordered by most recent first
    query = query.offset(skip).limit(limit).order_by(Quest.assigned_at.desc())
    result = await session.execute(query)
    quests = result.scalars().all()

    return QuestList(items=quests, total=total, skip=skip, limit=limit)
