from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from geoalchemy2.functions import ST_SetSRID, ST_Point
import pygeohash as geohash

from app.core.database import get_async_session
from app.core.auth import get_current_active_user, require_collector, require_admin
from app.core.config import settings
from app.models.user import User
from app.models.quest import Quest, QuestStatus
from app.schemas.quest import QuestCreate, QuestUpdate, QuestResponse, QuestList

router = APIRouter(prefix="/quests", tags=["CleanQuests"])


@router.post("", response_model=QuestResponse, status_code=status.HTTP_201_CREATED)
async def create_quest(
    quest_data: QuestCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Create a new CleanQuest (citizen reports waste)"""
    # Calculate geohash
    gh = geohash.encode(quest_data.location.latitude, quest_data.location.longitude, precision=8)
    # Extract ward-level geohash (first 5 chars)
    ward_gh = gh[:5]

    # Determine bounty based on waste type
    bounty_map = {
        "organic": settings.DEFAULT_QUEST_BOUNTY_ORGANIC,
        "recyclable": settings.DEFAULT_QUEST_BOUNTY_RECYCLABLE,
        "general": settings.DEFAULT_QUEST_BOUNTY_GENERAL,
        "e_waste": settings.DEFAULT_QUEST_BOUNTY_RECYCLABLE,
    }
    bounty = bounty_map.get(quest_data.waste_type, settings.DEFAULT_QUEST_BOUNTY_GENERAL)

    # Create quest
    quest = Quest(
        reporter_id=current_user.id,
        title=quest_data.title,
        description=quest_data.description,
        location=f"POINT({quest_data.location.longitude} {quest_data.location.latitude})",
        geohash=gh,
        ward_geohash=ward_gh,
        waste_type=quest_data.waste_type,
        severity=quest_data.severity,
        bounty_points=bounty,
        image_url=quest_data.image_url,
    )

    session.add(quest)
    await session.commit()
    await session.refresh(quest)

    return quest


@router.get("", response_model=QuestList)
async def list_quests(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    status_filter: Optional[QuestStatus] = None,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """List all quests with optional filters"""
    query = select(Quest)

    if status_filter:
        query = query.where(Quest.status == status_filter)

    # Get total count
    count_query = select(func.count()).select_from(Quest)
    if status_filter:
        count_query = count_query.where(Quest.status == status_filter)

    total_result = await session.execute(count_query)
    total = total_result.scalar()

    # Get quests
    query = query.offset(skip).limit(limit).order_by(Quest.created_at.desc())
    result = await session.execute(query)
    quests = result.scalars().all()

    return QuestList(items=quests, total=total, skip=skip, limit=limit)


@router.get("/{quest_id}", response_model=QuestResponse)
async def get_quest(
    quest_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Get a specific quest by ID"""
    result = await session.execute(select(Quest).where(Quest.id == quest_id))
    quest = result.scalar_one_or_none()

    if not quest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quest not found",
        )

    return quest


@router.patch("/{quest_id}/assign", response_model=QuestResponse)
async def assign_quest(
    quest_id: UUID,
    current_user: User = Depends(require_collector),
    session: AsyncSession = Depends(get_async_session),
):
    """Collector assigns themselves to a quest"""
    result = await session.execute(select(Quest).where(Quest.id == quest_id))
    quest = result.scalar_one_or_none()

    if not quest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quest not found",
        )

    if quest.status != QuestStatus.REPORTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quest is not available for assignment",
        )

    quest.collector_id = current_user.id
    quest.status = QuestStatus.ASSIGNED

    await session.commit()
    await session.refresh(quest)

    return quest


@router.patch("/{quest_id}", response_model=QuestResponse)
async def update_quest(
    quest_id: UUID,
    quest_update: QuestUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Update quest (collector submits photos, admin verifies)"""
    result = await session.execute(select(Quest).where(Quest.id == quest_id))
    quest = result.scalar_one_or_none()

    if not quest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quest not found",
        )

    # Only collector or admin can update
    if quest.collector_id != current_user.id and current_user.user_type.value != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this quest",
        )

    # Update fields
    for field, value in quest_update.model_dump(exclude_unset=True).items():
        setattr(quest, field, value)

    await session.commit()
    await session.refresh(quest)

    return quest


@router.get("/nearby", response_model=List[QuestResponse])
async def get_nearby_quests(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(5.0, gt=0, le=50),
    current_user: User = Depends(require_collector),
    session: AsyncSession = Depends(get_async_session),
):
    """Get quests near a location (for collectors)"""
    # This is a simplified version - in production use PostGIS ST_Distance
    query = select(Quest).where(Quest.status == QuestStatus.REPORTED).limit(20)
    result = await session.execute(query)
    quests = result.scalars().all()

    return quests
