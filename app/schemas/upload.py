from typing import Optional
from pydantic import BaseModel, Field


class ImageUploadResponse(BaseModel):
    """Schema for image upload response"""
    url: str = Field(..., description="Public URL of the uploaded image")
    filename: str = Field(..., description="Stored filename")
    content_type: str = Field(..., description="MIME type of the image")
    size_bytes: int = Field(..., description="Size of the image in bytes")

    model_config = {
        "json_schema_extra": {
            "example": {
                "url": "https://storage.googleapis.com/bucket/images/abc123.jpg",
                "filename": "abc123.jpg",
                "content_type": "image/jpeg",
                "size_bytes": 245678
            }
        }
    }


class QRCodeResponse(BaseModel):
    """Schema for QR code generation response"""
    qr_code_url: str = Field(..., description="URL to the generated QR code image")
    qr_data: str = Field(..., description="Data encoded in the QR code")
    expires_at: Optional[str] = Field(None, description="Expiration timestamp if applicable")

    model_config = {
        "json_schema_extra": {
            "example": {
                "qr_code_url": "https://storage.example.com/qr/kabadiwala-123.png",
                "qr_data": "kabadiwala:123e4567-e89b-12d3-a456-426614174000:verify",
                "expires_at": "2024-12-31T23:59:59Z"
            }
        }
    }


class QRValidationRequest(BaseModel):
    """Schema for QR code validation request"""
    qr_data: str = Field(..., description="Data scanned from QR code")

    model_config = {
        "json_schema_extra": {
            "example": {
                "qr_data": "kabadiwala:123e4567-e89b-12d3-a456-426614174000:verify"
            }
        }
    }


class QRValidationResponse(BaseModel):
    """Schema for QR code validation response"""
    valid: bool
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    user_type: Optional[str] = None
    reputation_score: Optional[float] = None
    verified_transactions: Optional[int] = None
    message: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "valid": True,
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "user_name": "Karim Abdul",
                "user_type": "kabadiwala",
                "reputation_score": 4.8,
                "verified_transactions": 156,
                "message": "Verified Kabadiwala"
            }
        }
    }
