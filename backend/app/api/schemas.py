"""
Pydantic schemas for API request/response models.
"""

from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime


# ============== Auth Schemas ==============

class LoginRequest(BaseModel):
    """Login request body."""
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """Token response for login/refresh."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Refresh token request body."""
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Change password request body."""
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


# ============== User Schemas ==============

class UserBase(BaseModel):
    """Base user schema."""
    username: str = Field(..., min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    role: str = Field(default="user", pattern="^(admin|user)$")


class UserCreate(UserBase):
    """Schema for creating a new user."""
    password: str = Field(..., min_length=8, max_length=128)


class UserUpdate(BaseModel):
    """Schema for updating a user."""
    email: Optional[EmailStr] = None
    role: Optional[str] = Field(default=None, pattern="^(admin|user)$")
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """User response schema (without password)."""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserListResponse(BaseModel):
    """Paginated user list response."""
    users: list[UserResponse]
    total: int


class CurrentUserResponse(BaseModel):
    """Response for /auth/me endpoint."""
    id: int
    username: str
    email: Optional[str] = None
    role: str
    is_active: bool

    class Config:
        from_attributes = True


class ResetPasswordRequest(BaseModel):
    """Admin reset password request."""
    new_password: str = Field(..., min_length=8, max_length=128)
