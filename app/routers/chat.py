from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_

from app.core.database import get_async_session
from app.core.auth import get_current_active_user
from app.models.user import User
from app.models.listing import Listing, ListingStatus
from app.models.chat import Chat, ChatMessage, ChatStatus
from app.schemas.chat import (
    ChatCreate, ChatResponse, ChatList, ChatMessageCreate,
    ChatMessageResponse, ConfirmDealRequest
)

router = APIRouter(prefix="/chats", tags=["In-App Chat"])


@router.post("", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
async def create_chat(
    chat_data: ChatCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Create a new chat for a listing.
    
    Chat is created in LOCKED status until deal is confirmed.
    Only the buyer (kabadiwala) can initiate a chat on a listing.
    """
    # Get the listing
    result = await session.execute(select(Listing).where(Listing.id == chat_data.listing_id))
    listing = result.scalar_one_or_none()

    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Listing not found"
        )

    # Check if user is trying to create chat on their own listing
    if listing.seller_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create chat on your own listing"
        )

    # Check if chat already exists between these users for this listing
    existing_chat = await session.execute(
        select(Chat).where(
            Chat.listing_id == chat_data.listing_id,
            Chat.buyer_id == current_user.id
        )
    )
    if existing_chat.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chat already exists for this listing"
        )

    # Create chat (starts as LOCKED)
    chat = Chat(
        listing_id=chat_data.listing_id,
        seller_id=listing.seller_id,
        buyer_id=current_user.id,
        status=ChatStatus.LOCKED
    )

    session.add(chat)
    await session.commit()
    await session.refresh(chat)

    return chat


@router.get("", response_model=ChatList)
async def list_chats(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Get all chats for the current user (as buyer or seller)"""
    query = select(Chat).where(
        or_(Chat.seller_id == current_user.id, Chat.buyer_id == current_user.id)
    ).order_by(Chat.updated_at.desc())

    # Get total count
    count_query = select(func.count()).select_from(Chat).where(
        or_(Chat.seller_id == current_user.id, Chat.buyer_id == current_user.id)
    )
    total_result = await session.execute(count_query)
    total = total_result.scalar()

    # Get chats
    query = query.offset(skip).limit(limit)
    result = await session.execute(query)
    chats = result.scalars().all()

    return ChatList(items=chats, total=total)


@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat(
    chat_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Get a specific chat with messages"""
    result = await session.execute(select(Chat).where(Chat.id == chat_id))
    chat = result.scalar_one_or_none()

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )

    # Check user is part of this chat
    if chat.seller_id != current_user.id and chat.buyer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this chat"
        )

    return chat


@router.post("/{chat_id}/confirm-deal", response_model=ChatResponse)
async def confirm_deal(
    chat_id: UUID,
    confirm_data: ConfirmDealRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Confirm deal to unlock the chat.
    
    Both seller and buyer must confirm for the chat to be unlocked.
    This is typically done after a bid is accepted.
    """
    result = await session.execute(select(Chat).where(Chat.id == chat_id))
    chat = result.scalar_one_or_none()

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )

    # Check user is part of this chat
    if chat.seller_id != current_user.id and chat.buyer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to confirm this deal"
        )

    if confirm_data.confirm:
        chat.deal_confirmed = True
        chat.status = ChatStatus.UNLOCKED

    await session.commit()
    await session.refresh(chat)

    return chat


@router.post("/{chat_id}/messages", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    chat_id: UUID,
    message_data: ChatMessageCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Send a message in a chat.
    
    Chat must be UNLOCKED (deal confirmed) to send messages.
    """
    result = await session.execute(select(Chat).where(Chat.id == chat_id))
    chat = result.scalar_one_or_none()

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )

    # Check user is part of this chat
    if chat.seller_id != current_user.id and chat.buyer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to send messages in this chat"
        )

    # Check chat is unlocked
    if chat.status == ChatStatus.LOCKED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chat is locked. Confirm the deal first to unlock messaging."
        )

    if chat.status == ChatStatus.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chat is closed"
        )

    # Create message
    message = ChatMessage(
        chat_id=chat_id,
        sender_id=current_user.id,
        content=message_data.content
    )

    session.add(message)
    await session.commit()
    await session.refresh(message)

    return message


@router.get("/{chat_id}/messages", response_model=List[ChatMessageResponse])
async def get_messages(
    chat_id: UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Get messages in a chat"""
    result = await session.execute(select(Chat).where(Chat.id == chat_id))
    chat = result.scalar_one_or_none()

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )

    # Check user is part of this chat
    if chat.seller_id != current_user.id and chat.buyer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view messages in this chat"
        )

    # Get messages
    query = select(ChatMessage).where(
        ChatMessage.chat_id == chat_id
    ).order_by(ChatMessage.created_at.asc()).offset(skip).limit(limit)

    result = await session.execute(query)
    messages = result.scalars().all()

    # Mark messages as read for the receiver
    for msg in messages:
        if msg.sender_id != current_user.id and not msg.is_read:
            msg.is_read = True

    await session.commit()

    return messages


@router.post("/{chat_id}/close", response_model=ChatResponse)
async def close_chat(
    chat_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Close a chat (usually after transaction is complete)"""
    result = await session.execute(select(Chat).where(Chat.id == chat_id))
    chat = result.scalar_one_or_none()

    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )

    # Check user is part of this chat
    if chat.seller_id != current_user.id and chat.buyer_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to close this chat"
        )

    chat.status = ChatStatus.CLOSED
    await session.commit()
    await session.refresh(chat)

    return chat
