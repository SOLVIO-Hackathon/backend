import uuid
import enum
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Boolean, Enum as SQLEnum, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.listing import Listing


class ChatStatus(str, enum.Enum):
    """Chat status states"""
    LOCKED = "locked"
    UNLOCKED = "unlocked"
    CLOSED = "closed"


class Chat(Base):
    """Chat model for in-app messaging between users"""
    __tablename__ = "chats"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    listing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("listings.id"), nullable=False, index=True
    )
    seller_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    buyer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )

    status: Mapped[ChatStatus] = mapped_column(
        SQLEnum(ChatStatus), default=ChatStatus.LOCKED, index=True
    )
    deal_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    listing: Mapped["Listing"] = relationship("Listing", backref="chats")
    seller: Mapped["User"] = relationship("User", foreign_keys=[seller_id])
    buyer: Mapped["User"] = relationship("User", foreign_keys=[buyer_id])
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage", back_populates="chat", order_by="ChatMessage.created_at"
    )

    def __repr__(self) -> str:
        return f"<Chat {self.id} - {self.status}>"


class ChatMessage(Base):
    """Chat message model"""
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    chat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chats.id"), nullable=False, index=True
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    chat: Mapped["Chat"] = relationship("Chat", back_populates="messages")
    sender: Mapped["User"] = relationship("User")

    def __repr__(self) -> str:
        return f"<ChatMessage {self.id} - Chat {self.chat_id}>"
