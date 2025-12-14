"""
User management API routes.
Admin-only endpoints for managing users.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime

from ...models import get_db, User, UserRole
from ...core.security import get_password_hash
from ..schemas import (
    UserCreate,
    UserUpdate,
    UserResponse,
    UserListResponse,
    ResetPasswordRequest
)
from ..deps import require_admin

router = APIRouter(prefix="/users", tags=["User Management"])


@router.get("", response_model=UserListResponse)
async def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    List all users (admin only).

    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    """
    total = db.query(User).count()
    users = db.query(User).order_by(User.created_at.desc()).offset(skip).limit(limit).all()

    return UserListResponse(
        users=[UserResponse.model_validate(u) for u in users],
        total=total
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new user (admin only).

    - **username**: Unique username (3-50 characters)
    - **email**: Optional email address
    - **password**: Password (min 8 characters)
    - **role**: User role ('admin' or 'user')
    """
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    # Check if email already exists (if provided)
    if user_data.email:
        existing_email = db.query(User).filter(User.email == user_data.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

    # Create new user
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        role=user_data.role,
        is_active=True
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return UserResponse.model_validate(new_user)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get user by ID (admin only).
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return UserResponse.model_validate(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Update user (admin only).

    - **email**: New email address
    - **role**: New role ('admin' or 'user')
    - **is_active**: Activate/deactivate user
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Prevent admin from deactivating themselves
    if user.id == admin_user.id and user_data.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account"
        )

    # Prevent admin from demoting themselves
    if user.id == admin_user.id and user_data.role == UserRole.USER.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot demote your own account"
        )

    # Check email uniqueness if changing
    if user_data.email and user_data.email != user.email:
        existing_email = db.query(User).filter(User.email == user_data.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

    # Update fields
    if user_data.email is not None:
        user.email = user_data.email
    if user_data.role is not None:
        user.role = user_data.role
    if user_data.is_active is not None:
        user.is_active = user_data.is_active

    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    return UserResponse.model_validate(user)


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Delete user (admin only).

    Cannot delete your own account.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Prevent admin from deleting themselves
    if user.id == admin_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    db.delete(user)
    db.commit()

    return {"message": f"User '{user.username}' deleted successfully"}


@router.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    request: ResetPasswordRequest,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Reset user password (admin only).

    - **new_password**: New password for the user (min 8 characters)
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    user.hashed_password = get_password_hash(request.new_password)
    user.updated_at = datetime.utcnow()
    db.commit()

    return {"message": f"Password reset successfully for user '{user.username}'"}
