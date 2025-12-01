from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_async_session
from app.core.auth import get_current_active_user, require_kabadiwala
from app.models.user import User, UserType
from app.schemas.upload import (
    ImageUploadResponse, QRCodeResponse, QRValidationRequest, QRValidationResponse
)
from app.services.firebase_storage import get_storage_service
from app.services.qr_service import get_qr_service

router = APIRouter(prefix="/upload", tags=["Upload & QR"])


@router.post("/image", response_model=ImageUploadResponse)
async def upload_image(
    file: UploadFile = File(..., description="Image file to upload"),
    folder: str = Query("uploads", description="Storage folder"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Upload an image to Firebase Storage.
    
    Supported formats: JPEG, PNG, WebP, GIF
    Maximum size: 10MB (configurable)
    
    Returns the public URL of the uploaded image.
    """
    storage_service = get_storage_service()

    result = await storage_service.upload_image(
        file=file,
        folder=folder,
        user_id=str(current_user.id)
    )

    return ImageUploadResponse(**result)


@router.post("/quest-image", response_model=ImageUploadResponse)
async def upload_quest_image(
    file: UploadFile = File(..., description="Quest image to upload"),
    current_user: User = Depends(get_current_active_user),
):
    """Upload an image for a quest (waste photo)"""
    storage_service = get_storage_service()

    result = await storage_service.upload_image(
        file=file,
        folder="quests",
        user_id=str(current_user.id)
    )

    return ImageUploadResponse(**result)


@router.post("/listing-image", response_model=ImageUploadResponse)
async def upload_listing_image(
    file: UploadFile = File(..., description="Listing image to upload"),
    current_user: User = Depends(get_current_active_user),
):
    """Upload an image for an e-waste listing"""
    storage_service = get_storage_service()

    result = await storage_service.upload_image(
        file=file,
        folder="listings",
        user_id=str(current_user.id)
    )

    return ImageUploadResponse(**result)


@router.get("/qr/kabadiwala", response_model=QRCodeResponse)
async def get_kabadiwala_qr(
    current_user: User = Depends(require_kabadiwala),
):
    """
    Generate QR code for kabadiwala verification.
    
    This QR code can be scanned by sellers to verify the kabadiwala's identity
    and reputation before completing a transaction.
    """
    qr_service = get_qr_service()

    result = qr_service.generate_kabadiwala_qr(
        user_id=str(current_user.id),
        user_name=current_user.full_name
    )

    return QRCodeResponse(**result)


@router.post("/qr/validate", response_model=QRValidationResponse)
async def validate_qr_code(
    validation_request: QRValidationRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Validate a scanned QR code.
    
    Parses the QR data and returns verification information
    about the kabadiwala or transaction.
    """
    qr_service = get_qr_service()

    # Parse QR data
    parsed = qr_service.parse_qr_data(validation_request.qr_data)

    if not parsed:
        return QRValidationResponse(
            valid=False,
            message="Invalid QR code format"
        )

    if parsed["type"] == "kabadiwala":
        # Validate kabadiwala
        user_id = parsed["user_id"]

        result = await session.execute(
            select(User).where(User.id == UUID(user_id))
        )
        user = result.scalar_one_or_none()

        if not user:
            return QRValidationResponse(
                valid=False,
                message="Kabadiwala not found"
            )

        if user.user_type != UserType.KABADIWALA:
            return QRValidationResponse(
                valid=False,
                message="User is not a registered kabadiwala"
            )

        if not user.is_active:
            return QRValidationResponse(
                valid=False,
                message="Kabadiwala account is inactive"
            )

        return QRValidationResponse(
            valid=True,
            user_id=str(user.id),
            user_name=user.full_name,
            user_type=user.user_type.value,
            reputation_score=user.reputation_score,
            verified_transactions=user.total_transactions,
            message="Verified Kabadiwala"
        )

    elif parsed["type"] == "transaction":
        # Transaction QR validation
        return QRValidationResponse(
            valid=True,
            message=f"Transaction QR code for transaction {parsed['transaction_id']}"
        )

    return QRValidationResponse(
        valid=False,
        message="Unknown QR code type"
    )


@router.get("/qr/transaction/{listing_id}", response_model=QRCodeResponse)
async def get_transaction_qr(
    listing_id: UUID,
    amount: float = Query(..., gt=0, description="Transaction amount"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Generate QR code for transaction confirmation.
    
    Used during physical pickup to confirm the transaction.
    """
    import uuid as uuid_module
    qr_service = get_qr_service()

    # Generate a unique transaction reference
    transaction_ref = str(uuid_module.uuid4())

    result = qr_service.generate_transaction_qr(
        transaction_id=transaction_ref,
        listing_id=str(listing_id),
        amount=amount
    )

    return QRCodeResponse(**result)
