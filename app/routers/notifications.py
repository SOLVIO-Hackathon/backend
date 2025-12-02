"""
In-app notification management endpoints.
"""

from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from pydantic import BaseModel

from app.core.database import get_async_session
from app.core.auth import get_current_active_user
from app.models.user import User
from app.models.notification import Notification


router = APIRouter(prefix="/notifications", tags=["Notifications"])


# Pydantic schemas
class NotificationResponse(BaseModel):
    """Notification response model"""
    id: str
    notification_type: str
    title: str
    message: str
    related_quest_id: Optional[str]
    metadata: dict
    is_read: bool
    created_at: str

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Paginated notification list"""
    items: List[NotificationResponse]
    total: int
    unread_count: int
    skip: int
    limit: int


@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    List user's notifications with pagination.
    
    - **skip**: Number of notifications to skip
    - **limit**: Maximum number of notifications to return
    - **unread_only**: If true, only return unread notifications
    """
    # Build query
    query = select(Notification).where(Notification.user_id == current_user.id)
    
    if unread_only:
        query = query.where(Notification.is_read == False)
    
    # Get total count
    count_query = select(func.count(Notification.id)).where(
        Notification.user_id == current_user.id
    )
    if unread_only:
        count_query = count_query.where(Notification.is_read == False)
    
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0
    
    # Get unread count
    unread_query = select(func.count(Notification.id)).where(
        and_(
            Notification.user_id == current_user.id,
            Notification.is_read == False
        )
    )
    unread_result = await session.execute(unread_query)
    unread_count = unread_result.scalar() or 0
    
    # Get notifications
    query = query.offset(skip).limit(limit).order_by(Notification.created_at.desc())
    result = await session.execute(query)
    notifications = result.scalars().all()
    
    # Convert to response models
    items = [
        NotificationResponse(
            id=str(n.id),
            notification_type=n.notification_type.value,
            title=n.title,
            message=n.message,
            related_quest_id=str(n.related_quest_id) if n.related_quest_id else None,
            metadata=n.extra_data or {},
            is_read=n.is_read,
            created_at=n.created_at.isoformat()
        )
        for n in notifications
    ]
    
    return NotificationListResponse(
        items=items,
        total=total,
        unread_count=unread_count,
        skip=skip,
        limit=limit
    )


@router.patch("/{notification_id}/read", status_code=status.HTTP_200_OK)
async def mark_notification_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Mark a single notification as read.
    """
    # Get notification
    query = select(Notification).where(
        and_(
            Notification.id == notification_id,
            Notification.user_id == current_user.id
        )
    )
    result = await session.execute(query)
    notification = result.scalar_one_or_none()
    
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    # Mark as read
    notification.is_read = True
    await session.commit()
    
    return {"message": "Notification marked as read"}


@router.post("/mark-all-read", status_code=status.HTTP_200_OK)
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Mark all user's notifications as read.
    """
    # Get all unread notifications
    query = select(Notification).where(
        and_(
            Notification.user_id == current_user.id,
            Notification.is_read == False
        )
    )
    result = await session.execute(query)
    notifications = result.scalars().all()
    
    # Mark all as read
    for notification in notifications:
        notification.is_read = True
    
    await session.commit()
    
    return {
        "message": f"Marked {len(notifications)} notifications as read",
        "count": len(notifications)
    }
