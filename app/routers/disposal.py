from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from geoalchemy2.functions import ST_X, ST_Y, ST_DWithin, ST_Distance, ST_SetSRID, ST_Point

from app.core.database import get_async_session
from app.core.auth import get_current_active_user, require_admin
from app.models.user import User
from app.models.disposal_point import DisposalPoint, DisposalPointType
from app.schemas.disposal import (
    DisposalPointCreate, DisposalPointResponse, DisposalPointList,
    RouteResponse, RouteStep, NearestDisposalResponse
)
from app.schemas.common import LocationSchema
from app.services.routing_service import get_routing_service

router = APIRouter(prefix="/disposal", tags=["Waste Disposal Routing"])


@router.post("", response_model=DisposalPointResponse, status_code=status.HTTP_201_CREATED)
async def create_disposal_point(
    point_data: DisposalPointCreate,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """Create a new disposal point (Admin only)"""
    disposal_point = DisposalPoint(
        name=point_data.name,
        description=point_data.description,
        address=point_data.address,
        point_type=point_data.point_type,
        location=f"POINT({point_data.location.longitude} {point_data.location.latitude})",
        operating_hours=point_data.operating_hours,
        contact_phone=point_data.contact_phone,
        accepted_waste_types=point_data.accepted_waste_types
    )

    session.add(disposal_point)
    await session.commit()
    await session.refresh(disposal_point)

    return disposal_point


@router.get("", response_model=DisposalPointList)
async def list_disposal_points(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    point_type: Optional[DisposalPointType] = None,
    waste_type: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """List all disposal points with optional filters"""
    query = select(DisposalPoint).where(DisposalPoint.is_active == True)

    if point_type:
        query = query.where(DisposalPoint.point_type == point_type)

    if waste_type:
        query = query.where(DisposalPoint.accepted_waste_types.ilike(f"%{waste_type}%"))

    # Get total count
    count_query = select(func.count()).select_from(DisposalPoint).where(DisposalPoint.is_active == True)
    if point_type:
        count_query = count_query.where(DisposalPoint.point_type == point_type)
    if waste_type:
        count_query = count_query.where(DisposalPoint.accepted_waste_types.ilike(f"%{waste_type}%"))

    total_result = await session.execute(count_query)
    total = total_result.scalar()

    # Get points
    query = query.offset(skip).limit(limit)
    result = await session.execute(query)
    points = result.scalars().all()

    return DisposalPointList(items=points, total=total)


@router.get("/nearby", response_model=List[NearestDisposalResponse])
async def get_nearby_disposal_points(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(10.0, gt=0, le=100),
    waste_type: Optional[str] = None,
    limit: int = Query(5, ge=1, le=20),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get nearest disposal points to a location.
    
    Uses PostGIS for efficient geospatial queries.
    Returns disposal points sorted by distance.
    """
    # Convert radius to meters for PostGIS
    radius_meters = radius_km * 1000

    # Build query with distance calculation
    user_point = ST_SetSRID(ST_Point(longitude, latitude), 4326)

    query = select(
        DisposalPoint,
        ST_X(DisposalPoint.location).label('lng'),
        ST_Y(DisposalPoint.location).label('lat'),
        ST_Distance(
            DisposalPoint.location,
            user_point
        ).label('distance')
    ).where(
        DisposalPoint.is_active == True,
        ST_DWithin(DisposalPoint.location, user_point, radius_meters)
    )

    if waste_type:
        query = query.where(DisposalPoint.accepted_waste_types.ilike(f"%{waste_type}%"))

    query = query.order_by('distance').limit(limit)

    result = await session.execute(query)
    rows = result.all()

    # Get routing service for distance calculations
    routing_service = get_routing_service()

    responses = []
    for row in rows:
        point = row[0]
        dest_lng = row.lng
        dest_lat = row.lat
        distance_degrees = row.distance

        # Approximate conversion from degrees to km (at equator, 1 degree ≈ 111 km)
        distance_km = distance_degrees * 111

        # Get actual route (optional - can be slow for many points)
        route = await routing_service.get_route(
            latitude, longitude, dest_lat, dest_lng
        )

        if route:
            distance_km = route.distance_km
            duration_minutes = route.duration_minutes
            route_geometry = route.route_geometry
        else:
            # Estimate duration based on average speed of 30 km/h
            duration_minutes = (distance_km / 30) * 60
            route_geometry = None

        responses.append(NearestDisposalResponse(
            disposal_point=point,
            distance_km=round(distance_km, 2),
            duration_minutes=round(duration_minutes, 1),
            route_geometry=route_geometry
        ))

    return responses


@router.get("/route/{disposal_point_id}", response_model=RouteResponse)
async def get_route_to_disposal(
    disposal_point_id: UUID,
    latitude: float = Query(..., ge=-90, le=90, description="Origin latitude"),
    longitude: float = Query(..., ge=-180, le=180, description="Origin longitude"),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Get detailed route from origin to a specific disposal point.
    
    Uses OpenStreetMap/OSRM for routing.
    """
    # Get disposal point with coordinates
    query = select(
        DisposalPoint,
        ST_X(DisposalPoint.location).label('lng'),
        ST_Y(DisposalPoint.location).label('lat')
    ).where(DisposalPoint.id == disposal_point_id)

    result = await session.execute(query)
    row = result.one_or_none()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Disposal point not found"
        )

    disposal_point = row[0]
    dest_lng = row.lng
    dest_lat = row.lat

    # Get route from OSRM
    routing_service = get_routing_service()
    route = await routing_service.get_route(latitude, longitude, dest_lat, dest_lng)

    if not route:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Routing service unavailable"
        )

    return RouteResponse(
        origin=LocationSchema(latitude=latitude, longitude=longitude),
        destination=disposal_point,
        distance_km=round(route.distance_km, 2),
        duration_minutes=round(route.duration_minutes, 1),
        route_geometry=route.route_geometry,
        steps=[
            RouteStep(
                instruction=step.instruction,
                distance_meters=step.distance_meters,
                duration_seconds=step.duration_seconds,
                maneuver=step.maneuver
            )
            for step in route.steps
        ]
    )


@router.get("/{disposal_point_id}", response_model=DisposalPointResponse)
async def get_disposal_point(
    disposal_point_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Get a specific disposal point by ID"""
    result = await session.execute(
        select(DisposalPoint).where(DisposalPoint.id == disposal_point_id)
    )
    point = result.scalar_one_or_none()

    if not point:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Disposal point not found"
        )

    return point


@router.delete("/{disposal_point_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_disposal_point(
    disposal_point_id: UUID,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """Delete a disposal point (Admin only) - soft delete by deactivating"""
    result = await session.execute(
        select(DisposalPoint).where(DisposalPoint.id == disposal_point_id)
    )
    point = result.scalar_one_or_none()

    if not point:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Disposal point not found"
        )

    point.is_active = False
    await session.commit()
