from typing import List, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_async_session
from app.core.auth import require_admin, get_current_active_user
from app.core.config import settings
from app.models.user import User
from app.models.quest import Quest, QuestStatus
from app.models.admin_review import AdminReview, ReviewStatus, FlagReason
from app.schemas.admin_review import (
    AdminReviewCreate, AdminReviewUpdate, AdminReviewResponse, AdminReviewList
)

router = APIRouter(prefix="/admin/reviews", tags=["Admin Review"])


@router.post("", response_model=AdminReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_review(
    review_data: AdminReviewCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Create an admin review for a flagged quest.
    
    This is typically called automatically by the AI service when confidence is low,
    or manually when suspicious activity is detected.
    """
    # Verify quest exists
    result = await session.execute(select(Quest).where(Quest.id == review_data.quest_id))
    quest = result.scalar_one_or_none()

    if not quest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quest not found"
        )

    # Check if review already exists for this quest
    existing = await session.execute(
        select(AdminReview).where(
            AdminReview.quest_id == review_data.quest_id,
            AdminReview.status == ReviewStatus.PENDING
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Pending review already exists for this quest"
        )

    # Create review
    review = AdminReview(
        quest_id=review_data.quest_id,
        flag_reason=review_data.flag_reason,
        ai_confidence_score=review_data.ai_confidence_score,
        ai_notes=review_data.ai_notes,
        status=ReviewStatus.PENDING
    )

    session.add(review)
    await session.commit()
    await session.refresh(review)

    return review


@router.get("", response_model=AdminReviewList)
async def list_reviews(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status_filter: Optional[ReviewStatus] = None,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """List all admin reviews (Admin only)"""
    query = select(AdminReview)

    if status_filter:
        query = query.where(AdminReview.status == status_filter)

    # Get total and pending counts
    total_result = await session.execute(
        select(func.count()).select_from(AdminReview)
        .where(AdminReview.status == status_filter if status_filter else True)
    )
    total = total_result.scalar()

    pending_result = await session.execute(
        select(func.count()).select_from(AdminReview)
        .where(AdminReview.status == ReviewStatus.PENDING)
    )
    pending_count = pending_result.scalar()

    # Get reviews
    query = query.order_by(AdminReview.created_at.desc()).offset(skip).limit(limit)
    result = await session.execute(query)
    reviews = result.scalars().all()

    return AdminReviewList(items=reviews, total=total, pending_count=pending_count)


@router.get("/pending", response_model=AdminReviewList)
async def list_pending_reviews(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """List all pending reviews that need admin attention (Admin only)"""
    query = select(AdminReview).where(AdminReview.status == ReviewStatus.PENDING)

    # Get counts
    total_result = await session.execute(
        select(func.count()).select_from(AdminReview)
        .where(AdminReview.status == ReviewStatus.PENDING)
    )
    total = total_result.scalar()

    # Get reviews
    query = query.order_by(AdminReview.created_at.asc()).offset(skip).limit(limit)
    result = await session.execute(query)
    reviews = result.scalars().all()

    return AdminReviewList(items=reviews, total=total, pending_count=total)


@router.get("/{review_id}", response_model=AdminReviewResponse)
async def get_review(
    review_id: UUID,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """Get a specific review by ID (Admin only)"""
    result = await session.execute(select(AdminReview).where(AdminReview.id == review_id))
    review = result.scalar_one_or_none()

    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )

    return review


@router.patch("/{review_id}", response_model=AdminReviewResponse)
async def update_review(
    review_id: UUID,
    review_update: AdminReviewUpdate,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Update a review decision (Admin only).
    
    This is the approval/rejection workflow for flagged quests.
    """
    result = await session.execute(select(AdminReview).where(AdminReview.id == review_id))
    review = result.scalar_one_or_none()

    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review not found"
        )

    if review.status != ReviewStatus.PENDING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Review has already been processed"
        )

    # Update review
    review.status = review_update.status
    review.admin_notes = review_update.admin_notes
    review.reviewer_id = current_user.id
    review.reviewed_at = datetime.utcnow()

    # Update the associated quest based on decision
    quest_result = await session.execute(select(Quest).where(Quest.id == review.quest_id))
    quest = quest_result.scalar_one_or_none()

    if quest:
        if review_update.status == ReviewStatus.APPROVED:
            quest.status = QuestStatus.VERIFIED
            quest.verified_at = datetime.utcnow()
        elif review_update.status == ReviewStatus.REJECTED:
            quest.status = QuestStatus.REJECTED

    await session.commit()
    await session.refresh(review)

    return review


@router.post("/flag-quest/{quest_id}", response_model=AdminReviewResponse)
async def flag_quest_for_review(
    quest_id: UUID,
    flag_reason: FlagReason = Query(..., description="Reason for flagging"),
    notes: Optional[str] = Query(None, description="Additional notes"),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Flag a quest for admin review.
    
    Can be called by users to report suspicious activity,
    or by AI service when confidence is low.
    """
    # Verify quest exists
    result = await session.execute(select(Quest).where(Quest.id == quest_id))
    quest = result.scalar_one_or_none()

    if not quest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quest not found"
        )

    # Check if pending review already exists
    existing = await session.execute(
        select(AdminReview).where(
            AdminReview.quest_id == quest_id,
            AdminReview.status == ReviewStatus.PENDING
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Quest is already flagged for review"
        )

    # Create review
    review = AdminReview(
        quest_id=quest_id,
        flag_reason=flag_reason,
        ai_confidence_score=quest.ai_verification_score,
        ai_notes=notes,
        status=ReviewStatus.PENDING
    )

    session.add(review)
    await session.commit()
    await session.refresh(review)

    return review


async def auto_flag_low_confidence_quest(
    quest_id: UUID,
    confidence_score: float,
    ai_notes: str,
    session: AsyncSession
) -> Optional[AdminReview]:
    """
    Automatically flag a quest for review if AI confidence is below threshold.
    
    This function is called by the AI verification service.
    """
    threshold = settings.AI_VERIFICATION_CONFIDENCE_THRESHOLD

    if confidence_score >= threshold:
        return None

    # Check if already flagged
    existing = await session.execute(
        select(AdminReview).where(
            AdminReview.quest_id == quest_id,
            AdminReview.status == ReviewStatus.PENDING
        )
    )
    if existing.scalar_one_or_none():
        return None

    # Create review
    review = AdminReview(
        quest_id=quest_id,
        flag_reason=FlagReason.LOW_AI_CONFIDENCE,
        ai_confidence_score=confidence_score,
        ai_notes=ai_notes,
        status=ReviewStatus.PENDING
    )

    session.add(review)
    await session.commit()
    await session.refresh(review)

    return review
