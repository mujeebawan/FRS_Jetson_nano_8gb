"""
Security utilities for authentication.
Password hashing and JWT token management.
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
import os

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT Configuration from environment
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-this-in-production-use-openssl-rand-hex-32")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))


class TokenData(BaseModel):
    """Token payload data."""
    user_id: Optional[int] = None
    username: Optional[str] = None
    role: Optional[str] = None
    token_type: Optional[str] = None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash."""
    return pwd_context.hash(password)


def create_access_token(
    user_id: int,
    username: str,
    role: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create JWT access token.

    Args:
        user_id: User's database ID
        username: User's username
        role: User's role (admin/user)
        expires_delta: Custom expiration time

    Returns:
        Encoded JWT token string
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.utcnow()
    }

    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(
    user_id: int,
    expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create JWT refresh token.

    Args:
        user_id: User's database ID
        expires_delta: Custom expiration time

    Returns:
        Encoded JWT refresh token string
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire,
        "iat": datetime.utcnow()
    }

    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Optional[TokenData]:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string

    Returns:
        TokenData if valid, None if invalid
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        username = payload.get("username")
        role = payload.get("role")
        token_type = payload.get("type")

        if user_id is None:
            return None

        return TokenData(
            user_id=int(user_id),
            username=username,
            role=role,
            token_type=token_type
        )
    except JWTError:
        return None
