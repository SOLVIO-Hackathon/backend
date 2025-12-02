"""Pydantic schemas for notifications"""

from typing import Optional, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel

from app.models.notification import NotificationType, NotificationChannel


class NotificationResponse(BaseModel):
    """Schema for notification response"""

    id: UUID
    user_id: UUID
    notification_type: NotificationType
    channel: NotificationChannel
    title: str
    message: str
    related_quest_id: Optional[UUID]
    metadata: dict
    is_read: bool
    sent_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationList(BaseModel):
    """Schema for paginated notification list"""

    items: List[NotificationResponse]
    total: int
    unread_count: int
