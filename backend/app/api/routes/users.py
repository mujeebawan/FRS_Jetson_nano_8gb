"""
User management API routes.
Admin-only endpoints for managing users.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from ...models.database import get_db, User
from ...core.security import get_password_hash
from ..schemas import (
    UserCreate,
    UserUpdate,
    UserResponse,
    ResetPasswordRequest
)
from ..deps import require_admin

router = APIRouter(prefix="/users", tags=["User Management"])


@router.get("/", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    List all users (admin only).
    """
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: UserCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Create a new user (admin only).

    - **username**: Unique username (3-50 chars, alphanumeric)
    - **password**: Password (min 8 chars)
    - **email**: Optional email address
    - **role**: 'admin' or 'user' (default: 'user')
    """
    # Check if username exists
    existing = db.query(User).filter(User.username == request.username.lower()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )

    # Check if email exists (if provided)
    if request.email:
        existing_email = db.query(User).filter(User.email == request.email.lower()).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )

    # Create user
    user = User(
        username=request.username.lower(),
        email=request.email.lower() if request.email else None,
        hashed_password=get_password_hash(request.password),
        role=request.role
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get user details (admin only).
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    request: UserUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Update user (admin only).

    - **email**: New email address
    - **role**: New role ('admin' or 'user')
    - **is_active**: Account status
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Prevent disabling yourself
    if user.id == admin.id and request.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot disable your own account"
        )

    # Prevent removing your own admin role
    if user.id == admin.id and request.role == "user":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove your own admin role"
        )

    # Check email uniqueness if changed
    if request.email and request.email.lower() != user.email:
        existing = db.query(User).filter(
            User.email == request.email.lower(),
            User.id != user_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )

    # Update fields
    if request.email is not None:
        user.email = request.email.lower() if request.email else None
    if request.role is not None:
        user.role = request.role
    if request.is_active is not None:
        user.is_active = request.is_active

    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Delete user (admin only).
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    # Prevent deleting yourself
    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )

    db.delete(user)
    db.commit()


@router.post("/{user_id}/reset-password")
async def reset_user_password(
    user_id: int,
    request: ResetPasswordRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Reset user password (admin only).

    - **new_password**: New password (min 8 chars)
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

    return {"message": f"Password reset for user '{user.username}'"}
