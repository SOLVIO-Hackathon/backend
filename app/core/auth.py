from typing import Optional
from uuid import UUID
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_async_session
from app.core.security import decode_access_token
from app.models.user import User, UserType

# Security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: AsyncSession = Depends(get_async_session),
) -> User:
    """Get current authenticated user"""
    token = credentials.credentials

    # Decode token
    payload = decode_access_token(token)
    user_id: str = payload.get("sub")

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )

    # Get user from database
    result = await session.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user",
        )
    return current_user


async def require_collector(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Require user to be a collector"""
    if current_user.user_type != UserType.COLLECTOR:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only collectors can access this endpoint",
        )
    return current_user


async def require_kabadiwala(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Require user to be a kabadiwala"""
    if current_user.user_type != UserType.KABADIWALA:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only kabadiwalas can access this endpoint",
        )
    return current_user


async def require_admin(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """Require user to be an admin"""
    if current_user.user_type != UserType.ADMIN and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can access this endpoint",
        )
    return current_user


# Optional auth - returns None if not authenticated
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    session: AsyncSession = Depends(get_async_session),
) -> Optional[User]:
    """Get current user if authenticated, otherwise return None"""
    if credentials is None:
        return None

    try:
        token = credentials.credentials
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")

        if user_id is None:
            return None

        result = await session.execute(select(User).where(User.id == UUID(user_id)))
        user = result.scalar_one_or_none()

        return user
    except Exception:
        return None
