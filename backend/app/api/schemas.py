"""
Pydantic schemas for API requests and responses.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


# ============== Authentication Schemas ==============

class LoginRequest(BaseModel):
    """Login request with username and password."""
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Change password request."""
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=100)

    @field_validator('new_password')
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        return v


class CurrentUserResponse(BaseModel):
    """Current user info response."""
    id: int
    username: str
    email: Optional[str] = None
    role: str
    is_active: bool

    class Config:
        from_attributes = True


# ============== User Management Schemas ==============

class UserCreate(BaseModel):
    """Create new user request."""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)
    email: Optional[str] = Field(None, max_length=255)
    role: str = Field(default="user", pattern="^(admin|user)$")

    @field_validator('username')
    @classmethod
    def username_alphanumeric(cls, v):
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username must be alphanumeric (underscores and hyphens allowed)')
        return v.lower()


class UserUpdate(BaseModel):
    """Update user request."""
    email: Optional[str] = Field(None, max_length=255)
    role: Optional[str] = Field(None, pattern="^(admin|user)$")
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    """User response (without password)."""
    id: int
    username: str
    email: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class ResetPasswordRequest(BaseModel):
    """Admin reset user password request."""
    new_password: str = Field(..., min_length=8, max_length=100)
