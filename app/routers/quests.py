from typing import List, Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from geoalchemy2.functions import ST_SetSRID, ST_Point, ST_X, ST_Y, ST_Distance
import pygeohash as geohash

from app.core.database import get_async_session
from app.core.auth import get_current_active_user, require_collector, require_admin
from app.core.config import settings
from app.models.user import User
from app.models.quest import Quest, QuestStatus
from app.models.transaction import Transaction, TransactionType, PaymentMethod, PaymentStatus
from app.models.disposal_point import DisposalPoint
from app.schemas.quest import QuestCreate, QuestUpdate, QuestResponse, QuestList
from app.utils.duplicate_detection import is_potential_duplicate
from app.services.ai_service import get_ai_service
from app.services.qr_service import get_qr_service
from app.services.routing_service import get_routing_service
from app.utils.exif_extraction import compare_metadata
from app.routers.admin_review import auto_flag_low_confidence_quest

router = APIRouter(prefix="/quests", tags=["CleanQuests"])


@router.post("", response_model=QuestResponse, status_code=status.HTTP_201_CREATED)
async def create_quest(
    quest_data: QuestCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Create a new CleanQuest (citizen reports waste).

    ✅ FEATURE 1: Duplicate Detection Integration
    - Checks for existing quests in the same location within time window
    - Prevents spam and duplicate reporting
    """
    # Calculate geohash
    gh = geohash.encode(quest_data.location.latitude, quest_data.location.longitude, precision=8)
    # Extract ward-level geohash (first 5 chars)
    ward_gh = gh[:5]

    # ✅ FEATURE 1: DUPLICATE DETECTION
    # Check for potential duplicates within the last 30 minutes in nearby locations
    nearby_query = select(Quest).where(
        Quest.ward_geohash == ward_gh,
        Quest.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0)  # Today
    ).order_by(Quest.created_at.desc()).limit(50)

    nearby_result = await session.execute(nearby_query)
    nearby_quests = nearby_result.scalars().all()

    for existing_quest in nearby_quests:
        is_duplicate, reason = is_potential_duplicate(
            new_lat=quest_data.location.latitude,
            new_lng=quest_data.location.longitude,
            new_timestamp=datetime.utcnow(),
            existing_geohash=existing_quest.geohash,
            existing_timestamp=existing_quest.created_at,
            location_precision=6,  # ~1.22km precision
            time_tolerance_minutes=30
        )

        if is_duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Duplicate quest detected: {reason}. Existing quest ID: {existing_quest.id}"
            )

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


@router.patch("/{quest_id}/assign", response_model=dict)
async def assign_quest(
    quest_id: UUID,
    current_user: User = Depends(require_collector),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Collector assigns themselves to a quest.

    ✅ FEATURE 3: QR Code Generation
    - Generates a QR code for the collector to use for verification
    """
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
    quest.assigned_at = datetime.utcnow()

    await session.commit()
    await session.refresh(quest)

    # ✅ FEATURE 3: GENERATE QR CODE FOR VERIFICATION
    qr_service = get_qr_service()
    qr_data = qr_service.generate_kabadiwala_qr(
        user_id=str(current_user.id),
        user_name=current_user.full_name,
        include_timestamp=True
    )

    return {
        "quest": quest,
        "qr_code": qr_data,
        "message": "Quest assigned successfully. Use the QR code for verification after cleanup."
    }


@router.post("/{quest_id}/complete", response_model=dict)
async def complete_quest(
    quest_id: UUID,
    quest_update: QuestUpdate,
    current_user: User = Depends(require_collector),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Collector completes a quest by submitting before/after photos.

    ✅ FEATURE 2: AI Verification Workflow
    - Automatically verifies cleanup using AI
    - Compares EXIF metadata (GPS, timestamp, device)
    - Checks before/after photo consistency
    - Auto-flags low confidence for admin review

    ✅ FEATURE 4: Waste Disposal Routing
    - Suggests nearest disposal points based on waste type
    - Provides routing information

    ✅ FEATURE 5: Bounty Payout Automation (triggers on verification)
    """
    result = await session.execute(select(Quest).where(Quest.id == quest_id))
    quest = result.scalar_one_or_none()

    if not quest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quest not found",
        )

    # Only collector can complete their assigned quest
    if quest.collector_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to complete this quest",
        )

    if quest.status not in [QuestStatus.ASSIGNED, QuestStatus.IN_PROGRESS]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quest is not in a completable state",
        )

    # Require both before and after photos
    if not quest_update.before_photo_url or not quest_update.after_photo_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both before and after photos are required to complete quest",
        )

    # Update quest with photos
    quest.before_photo_url = quest_update.before_photo_url
    quest.after_photo_url = quest_update.after_photo_url
    quest.before_photo_metadata = quest_update.before_photo_metadata
    quest.after_photo_metadata = quest_update.after_photo_metadata
    quest.status = QuestStatus.COMPLETED
    quest.completed_at = datetime.utcnow()

    # ✅ FEATURE 2: AI VERIFICATION WORKFLOW
    ai_service = get_ai_service()

    # Perform EXIF metadata comparison if available
    metadata_check = None
    if quest.before_photo_metadata and quest.after_photo_metadata:
        metadata_check = compare_metadata(
            quest.before_photo_metadata,
            quest.after_photo_metadata,
            gps_tolerance_meters=settings.EXIF_GPS_TOLERANCE_METERS,
            time_tolerance_minutes=settings.EXIF_TIME_TOLERANCE_MINUTES
        )

    # AI verification of before/after photos
    try:
        verification_result = await ai_service.verify_before_after_cleanup(
            before_image_url=quest.before_photo_url,
            after_image_url=quest.after_photo_url,
            expected_waste_type=quest.waste_type.value,
            metadata_comparison=metadata_check
        )

        quest.ai_verification_score = verification_result.confidence_score
        quest.verification_notes = f"AI: {verification_result.verification_decision}\n{verification_result.detailed_analysis}"

        # Auto-approve if high confidence, flag for review if low
        if verification_result.confidence_score >= settings.AI_VERIFICATION_CONFIDENCE_THRESHOLD:
            quest.status = QuestStatus.VERIFIED
            quest.verified_at = datetime.utcnow()

            # ✅ FEATURE 5: BOUNTY PAYOUT AUTOMATION
            # Create transaction for quest completion
            transaction = Transaction(
                transaction_type=TransactionType.QUEST_COMPLETION,
                user_id=current_user.id,
                quest_id=quest.id,
                amount=Decimal(str(quest.bounty_points)),
                currency="BDT",
                payment_method=PaymentMethod.WALLET,
                payment_status=PaymentStatus.COMPLETED,
                notes=f"Quest completion bounty: {quest.title}"
            )
            session.add(transaction)

            # Update collector reputation
            current_user.reputation_score += 1.0
            current_user.total_transactions += 1

            verification_message = "✅ Quest verified and bounty awarded!"
        else:
            # ✅ FEATURE 2: AUTO-FLAG LOW CONFIDENCE FOR ADMIN REVIEW
            # Low confidence - automatically flag for admin review
            ai_notes = f"Verification Decision: {verification_result.verification_decision}\n"
            ai_notes += f"Detailed Analysis: {verification_result.detailed_analysis}\n"
            if verification_result.fraud_indicators:
                ai_notes += f"Fraud Indicators: {', '.join(verification_result.fraud_indicators)}"

            admin_review = await auto_flag_low_confidence_quest(
                quest_id=quest.id,
                confidence_score=verification_result.confidence_score,
                ai_notes=ai_notes,
                session=session
            )

            verification_message = "⚠️ Quest completed but flagged for admin review due to low AI confidence."

    except Exception as e:
        quest.verification_notes = f"AI verification failed: {str(e)}"

        # ✅ FEATURE 2: AUTO-FLAG FAILED VERIFICATION FOR ADMIN REVIEW
        # AI verification failed - flag for manual admin review
        try:
            admin_review = await auto_flag_low_confidence_quest(
                quest_id=quest.id,
                confidence_score=0.0,  # Set to 0 to indicate failure
                ai_notes=f"AI verification failed with error: {str(e)}",
                session=session
            )
        except Exception:
            pass  # If auto-flagging fails, continue without blocking quest completion

        verification_message = "⚠️ Quest completed but AI verification failed. Flagged for manual review."

    # ✅ FEATURE 4: WASTE DISPOSAL ROUTING
    # Get quest location
    location_query = select(
        ST_X(Quest.location).label('lng'),
        ST_Y(Quest.location).label('lat')
    ).where(Quest.id == quest_id)
    loc_result = await session.execute(location_query)
    loc_row = loc_result.one()
    quest_lat = loc_row.lat
    quest_lng = loc_row.lng

    # Find nearest disposal points for the waste type
    user_point = ST_SetSRID(ST_Point(quest_lng, quest_lat), 4326)

    disposal_query = select(
        DisposalPoint,
        ST_X(DisposalPoint.location).label('disposal_lng'),
        ST_Y(DisposalPoint.location).label('disposal_lat'),
        ST_Distance(DisposalPoint.location, user_point).label('distance')
    ).where(
        DisposalPoint.is_active,
        DisposalPoint.accepted_waste_types.ilike(f"%{quest.waste_type.value}%")
    ).order_by('distance').limit(3)

    disposal_result = await session.execute(disposal_query)
    disposal_rows = disposal_result.all()

    # Get routing service
    routing_service = get_routing_service()
    nearest_disposal_points = []

    for row in disposal_rows:
        point = row[0]
        dest_lat = row.disposal_lat
        dest_lng = row.disposal_lng

        # Get route
        route = await routing_service.get_route(quest_lat, quest_lng, dest_lat, dest_lng)

        if route:
            nearest_disposal_points.append({
                "disposal_point": {
                    "id": str(point.id),
                    "name": point.name,
                    "address": point.address,
                    "point_type": point.point_type.value,
                    "latitude": dest_lat,
                    "longitude": dest_lng
                },
                "distance_km": round(route.distance_km, 2),
                "duration_minutes": round(route.duration_minutes, 1),
                "route_geometry": route.route_geometry
            })

    await session.commit()
    await session.refresh(quest)

    return {
        "quest": quest,
        "verification": {
            "status": quest.status.value,
            "confidence_score": quest.ai_verification_score,
            "message": verification_message,
            "metadata_check": metadata_check
        },
        "disposal_routing": {
            "message": f"Found {len(nearest_disposal_points)} nearby disposal points for {quest.waste_type.value} waste",
            "nearest_points": nearest_disposal_points
        }
    }


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
    """
    Get quests near a location (for collectors).
    Uses PostGIS for efficient spatial queries.
    """
    # Convert radius to meters for PostGIS
    radius_meters = radius_km * 1000
    user_point = ST_SetSRID(ST_Point(longitude, latitude), 4326)

    query = select(Quest).where(
        Quest.status == QuestStatus.REPORTED,
        ST_Distance(Quest.location, user_point) <= radius_meters
    ).order_by(
        ST_Distance(Quest.location, user_point)
    ).limit(20)

    result = await session.execute(query)
    quests = result.scalars().all()

    return quests


@router.get("/{quest_id}/disposal-route", response_model=List[dict])
async def get_quest_disposal_route(
    quest_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get disposal routing information for a quest.

    ✅ FEATURE 4: Waste Disposal Routing
    Returns nearest disposal points with routes.
    """
    result = await session.execute(select(Quest).where(Quest.id == quest_id))
    quest = result.scalar_one_or_none()

    if not quest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quest not found",
        )

    # Get quest location
    location_query = select(
        ST_X(Quest.location).label('lng'),
        ST_Y(Quest.location).label('lat')
    ).where(Quest.id == quest_id)
    loc_result = await session.execute(location_query)
    loc_row = loc_result.one()
    quest_lat = loc_row.lat
    quest_lng = loc_row.lng

    # Find nearest disposal points
    user_point = ST_SetSRID(ST_Point(quest_lng, quest_lat), 4326)

    disposal_query = select(
        DisposalPoint,
        ST_X(DisposalPoint.location).label('disposal_lng'),
        ST_Y(DisposalPoint.location).label('disposal_lat'),
        ST_Distance(DisposalPoint.location, user_point).label('distance')
    ).where(
        DisposalPoint.is_active,
        DisposalPoint.accepted_waste_types.ilike(f"%{quest.waste_type.value}%")
    ).order_by('distance').limit(5)

    disposal_result = await session.execute(disposal_query)
    disposal_rows = disposal_result.all()

    routing_service = get_routing_service()
    routes = []

    for row in disposal_rows:
        point = row[0]
        dest_lat = row.disposal_lat
        dest_lng = row.disposal_lng

        route = await routing_service.get_route(quest_lat, quest_lng, dest_lat, dest_lng)

        if route:
            routes.append({
                "disposal_point": {
                    "id": str(point.id),
                    "name": point.name,
                    "address": point.address,
                    "point_type": point.point_type.value,
                    "contact_phone": point.contact_phone,
                    "operating_hours": point.operating_hours,
                    "latitude": dest_lat,
                    "longitude": dest_lng
                },
                "distance_km": round(route.distance_km, 2),
                "duration_minutes": round(route.duration_minutes, 1),
                "route_geometry": route.route_geometry,
                "steps": [
                    {
                        "instruction": step.instruction,
                        "distance_meters": step.distance_meters,
                        "duration_seconds": step.duration_seconds,
                        "maneuver": step.maneuver
                    }
                    for step in route.steps
                ]
            })

    return routes
