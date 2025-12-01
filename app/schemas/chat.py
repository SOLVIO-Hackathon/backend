from typing import Optional, List
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.chat import ChatStatus


class ChatMessageCreate(BaseModel):
    """Schema for creating a chat message"""
    content: str = Field(..., min_length=1, max_length=2000)

    model_config = {
        "json_schema_extra": {
            "example": {
                "content": "Hello, I'm interested in your listing."
            }
        }
    }


class ChatMessageResponse(BaseModel):
    """Schema for chat message response"""
    id: UUID
    chat_id: UUID
    sender_id: UUID
    content: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatCreate(BaseModel):
    """Schema for creating a chat"""
    listing_id: UUID = Field(..., description="ID of the listing for this chat")
    buyer_id: UUID = Field(..., description="ID of the buyer initiating the chat")

    model_config = {
        "json_schema_extra": {
            "example": {
                "listing_id": "123e4567-e89b-12d3-a456-426614174000",
                "buyer_id": "456e4567-e89b-12d3-a456-426614174000"
            }
        }
    }


class ChatResponse(BaseModel):
    """Schema for chat response"""
    id: UUID
    listing_id: UUID
    seller_id: UUID
    buyer_id: UUID
    status: ChatStatus
    deal_confirmed: bool
    created_at: datetime
    updated_at: datetime
    messages: List[ChatMessageResponse] = []

    model_config = {"from_attributes": True}


class ChatList(BaseModel):
    """Schema for paginated chat list"""
    items: List[ChatResponse]
    total: int


class ConfirmDealRequest(BaseModel):
    """Schema for confirming a deal to unlock chat"""
    confirm: bool = Field(..., description="Set to true to confirm the deal")

    model_config = {
        "json_schema_extra": {
            "example": {
                "confirm": True
            }
        }
    }
