from typing import Optional
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field

from app.models.user import UserType


class UserBase(BaseModel):
    """Base user schema"""
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=255)
    phone_number: Optional[str] = Field(None, max_length=20)
    user_type: UserType = UserType.CITIZEN


class UserCreate(UserBase):
    """Schema for user registration"""
    password: str = Field(..., min_length=8, max_length=100)

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "user@example.com",
                "full_name": "John Doe",
                "phone_number": "+8801712345678",
                "user_type": "citizen",
                "password": "securePassword123"
            }
        }
    }


class UserUpdate(BaseModel):
    """Schema for updating user profile"""
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone_number: Optional[str] = Field(None, max_length=20)
    password: Optional[str] = Field(None, min_length=8, max_length=100)

    model_config = {
        "json_schema_extra": {
            "example": {
                "full_name": "John Updated Doe",
                "phone_number": "+8801712345679"
            }
        }
    }


class UserResponse(BaseModel):
    """Schema for user response (full details)"""
    id: UUID
    email: EmailStr
    full_name: str
    phone_number: Optional[str]
    user_type: UserType
    is_active: bool
    is_verified: bool
    is_sponsor: bool = False
    reputation_score: float
    total_transactions: int
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "email": "user@example.com",
                "full_name": "John Doe",
                "phone_number": "+8801712345678",
                "user_type": "citizen",
                "is_active": True,
                "is_verified": True,
                "is_sponsor": False,
                "reputation_score": 4.5,
                "total_transactions": 10,
                "created_at": "2024-01-01T00:00:00",
                "updated_at": "2024-01-01T00:00:00"
            }
        }
    }


class UserPublic(BaseModel):
    """Schema for public user info (limited)"""
    id: UUID
    full_name: str
    user_type: UserType
    reputation_score: float
    is_sponsor: bool = False

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "full_name": "John Doe",
                "user_type": "collector",
                "reputation_score": 4.7,
                "is_sponsor": False
            }
        }
    }


class UserLogin(BaseModel):
    """Schema for user login"""
    email: EmailStr
    password: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "email": "user@example.com",
                "password": "securePassword123"
            }
        }
    }


class TokenResponse(BaseModel):
    """Schema for JWT token response"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

    model_config = {
        "json_schema_extra": {
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "user": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "email": "user@example.com",
                    "full_name": "John Doe"
                }
            }
        }
    }
