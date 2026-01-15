"""
FastAPI dependencies for authentication and authorization.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from ..models.database import get_db, User
from ..core.security import decode_token

# OAuth2 scheme - expects token in Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token.

    Raises:
        HTTPException 401: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Decode token
    token_data = decode_token(token)
    if token_data is None:
        raise credentials_exception

    # Verify it's an access token (not refresh)
    if token_data.token_type != "access":
        raise credentials_exception

    # Get user from database
    user = db.query(User).filter(User.id == token_data.user_id).first()
    if user is None:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current active user.

    Raises:
        HTTPException 403: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    return current_user


async def require_admin(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Require admin role for access.

    Raises:
        HTTPException 403: If user is not admin
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


# Auth from query parameter - for image endpoints (browser can't send headers with img src)
async def get_user_from_token_param(
    token: str = None,
    db: Session = Depends(get_db)
) -> User:
    """
    Get user from token query parameter.
    Used for image endpoints where browser can't send Authorization header.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token required"
        )

    token_data = decode_token(token)
    if token_data is None or token_data.token_type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )

    user = db.query(User).filter(User.id == token_data.user_id).first()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )

    return user


# Optional auth - returns None if no token provided
async def get_optional_user(
    token: str = Depends(OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)),
    db: Session = Depends(get_db)
) -> User | None:
    """
    Get current user if token provided, otherwise return None.
    Useful for endpoints that work with or without authentication.
    """
    if token is None:
        return None

    token_data = decode_token(token)
    if token_data is None or token_data.token_type != "access":
        return None

    return db.query(User).filter(User.id == token_data.user_id).first()
