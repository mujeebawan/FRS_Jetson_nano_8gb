"""
Authentication API routes.
Login, refresh, logout, and current user endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from ...models import get_db, User
from ...core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token
)
from ..schemas import (
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    ChangePasswordRequest,
    CurrentUserResponse
)
from ..deps import get_current_active_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT tokens.

    - **username**: User's username
    - **password**: User's password

    Returns access and refresh tokens.
    """
    # Find user by username
    user = db.query(User).filter(User.username == request.username).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify password
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )

    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()

    # Create tokens
    access_token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role
    )
    refresh_token = create_refresh_token(user_id=user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token.

    - **refresh_token**: Valid refresh token

    Returns new access and refresh tokens.
    """
    # Decode refresh token
    token_data = decode_token(request.refresh_token)

    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Verify token type
    if token_data.token_type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Get user from database
    user = db.query(User).filter(User.id == token_data.user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )

    # Create new tokens (token rotation)
    access_token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role
    )
    new_refresh_token = create_refresh_token(user_id=user.id)

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer"
    )


@router.post("/logout")
async def logout(
    current_user: User = Depends(get_current_active_user)
):
    """
    Logout current user.

    Note: With stateless JWT, client should discard tokens.
    This endpoint exists for API completeness and potential
    future token blacklisting.
    """
    # In a stateless JWT system, logout is handled client-side
    # Future: Could implement token blacklisting here
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=CurrentUserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_active_user)
):
    """
    Get current authenticated user information.
    """
    return CurrentUserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        role=current_user.role,
        is_active=current_user.is_active
    )


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Change current user's password.

    - **current_password**: Current password for verification
    - **new_password**: New password (min 8 characters)
    """
    # Verify current password
    if not verify_password(request.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )

    # Update password
    current_user.hashed_password = get_password_hash(request.new_password)
    current_user.updated_at = datetime.utcnow()
    db.commit()

    return {"message": "Password changed successfully"}
