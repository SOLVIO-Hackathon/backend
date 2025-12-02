"""
Simple notification service for in-app notifications.
Can be extended to support email/SMS later.
"""

from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.notification import Notification, NotificationType, NotificationChannel
from app.models.quest import Quest
from app.models.user import User, UserType


class NotificationService:
    """Service for creating and managing notifications"""

    async def notify_quest_assigned(
        self, quest: Quest, collector: User, session: AsyncSession
    ):
        """Notify collector when quest is assigned to them"""
        notification = Notification(
            user_id=collector.id,
            notification_type=NotificationType.QUEST_ASSIGNED,
            channel=NotificationChannel.IN_APP,
            title="New Quest Assigned!",
            message=f"You've been assigned a new cleanup quest: {quest.title}",
            related_quest_id=quest.id,
            metadata={
                "quest_bounty": quest.bounty_points,
                "waste_type": quest.waste_type.value,
                "severity": quest.severity.value,
            },
        )
        session.add(notification)

    async def notify_quest_verified(
        self, quest: Quest, collector: User, session: AsyncSession
    ):
        """Notify collector when quest is verified and payment issued"""
        notification = Notification(
            user_id=collector.id,
            notification_type=NotificationType.QUEST_VERIFIED,
            channel=NotificationChannel.IN_APP,
            title="Quest Verified!",
            message=f"Your cleanup of '{quest.title}' has been verified. Bounty paid: {quest.bounty_points} BDT",
            related_quest_id=quest.id,
            metadata={
                "bounty_amount": quest.bounty_points,
                "ai_score": quest.ai_verification_score,
            },
        )
        session.add(notification)

    async def notify_quest_rejected(
        self, quest: Quest, collector: User, reason: str, session: AsyncSession
    ):
        """Notify collector when quest is rejected"""
        notification = Notification(
            user_id=collector.id,
            notification_type=NotificationType.QUEST_REJECTED,
            channel=NotificationChannel.IN_APP,
            title="Quest Rejected",
            message=f"Your cleanup of '{quest.title}' was rejected. Reason: {reason}",
            related_quest_id=quest.id,
            metadata={"rejection_reason": reason},
        )
        session.add(notification)

    async def notify_fraud_alert(
        self, user: User, fraud_score: float, session: AsyncSession
    ):
        """Notify admin about high fraud risk user"""
        # Get all admins
        admin_query = select(User).where(User.user_type == UserType.ADMIN)
        result = await session.execute(admin_query)
        admins = result.scalars().all()

        for admin in admins:
            notification = Notification(
                user_id=admin.id,
                notification_type=NotificationType.FRAUD_ALERT,
                channel=NotificationChannel.IN_APP,
                title="Fraud Alert",
                message=f"User {user.full_name} has high fraud risk score: {fraud_score:.2f}",
                metadata={"flagged_user_id": str(user.id), "fraud_score": fraud_score},
            )
            session.add(notification)


# Singleton
_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """Get or create notification service singleton"""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
