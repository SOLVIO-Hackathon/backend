from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_async_session
from app.models.complaint import Complaint
from app.schemas.complaint import ComplaintCreate, ComplaintOut

router = APIRouter(prefix="/complaints", tags=["Complaints"])


@router.get("/", response_model=list[ComplaintOut])
async def list_complaints(session: AsyncSession = Depends(get_async_session)):
    result = await session.execute(select(Complaint).order_by(Complaint.id.desc()))
    complaints = result.scalars().all()
    return complaints


@router.post("/", response_model=ComplaintOut, status_code=status.HTTP_201_CREATED)
async def create_complaint(payload: ComplaintCreate, session: AsyncSession = Depends(get_async_session)):
    complaint = Complaint(
        text=payload.text,
        language=payload.language,
        sentiment=payload.sentiment,
        confidence=payload.confidence,
        severity=payload.severity,
    )
    session.add(complaint)
    await session.flush()
    await session.refresh(complaint)
    return complaint
