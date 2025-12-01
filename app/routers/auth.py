from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_async_session
from app.core.security import verify_password, get_password_hash, create_access_token
from app.core.auth import get_current_active_user
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserResponse, UserLogin, TokenResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    session: AsyncSession = Depends(get_async_session),
):
    """Register a new user"""
    # Check if user already exists
    result = await session.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user
    user = User(
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        phone_number=user_data.phone_number,
        user_type=user_data.user_type,
    )

    session.add(user)
    await session.commit()
    await session.refresh(user)

    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    session: AsyncSession = Depends(get_async_session),
):
    """Login and get access token"""
    # Get user by email
    result = await session.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    # Create access token
    access_token = create_access_token(data={"sub": str(user.id)})

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user),
):
    """Get current user information"""
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_current_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Update current user profile"""
    # Update fields
    if user_update.full_name is not None:
        current_user.full_name = user_update.full_name

    if user_update.phone_number is not None:
        current_user.phone_number = user_update.phone_number

    if user_update.password is not None:
        current_user.hashed_password = get_password_hash(user_update.password)

    await session.commit()
    await session.refresh(current_user)

    return current_user


@router.post("/logout")
async def logout():
    """Logout (client should delete token)"""
    return {"message": "Successfully logged out"}


@router.patch("/me/sponsor", response_model=UserResponse)
async def toggle_sponsor_status(
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session),
):
    """Toggle sponsor status for current user"""
    current_user.is_sponsor = not current_user.is_sponsor
    await session.commit()
    await session.refresh(current_user)
    return current_user


@router.get("/sponsors", response_model=list)
async def get_sponsors(
    session: AsyncSession = Depends(get_async_session),
):
    """Get list of all sponsors (public endpoint)"""
    result = await session.execute(
        select(User)
        .where(User.is_sponsor.is_(True))
        .where(User.is_active.is_(True))
        .order_by(User.reputation_score.desc())
    )
    sponsors = result.scalars().all()
    
    return [
        {
            "id": str(sponsor.id),
            "full_name": sponsor.full_name,
            "user_type": sponsor.user_type.value,
            "reputation_score": sponsor.reputation_score,
        }
        for sponsor in sponsors
    ]
