"""
User model for authentication and authorization.
"""

from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum
from datetime import datetime
import enum

from .database import Base


class UserRole(str, enum.Enum):
    """User roles for RBAC."""
    ADMIN = "admin"
    USER = "user"


class User(Base):
    """
    User model for authentication.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    hashed_password = Column(String(255), nullable=False)

    # Role-based access control
    role = Column(String(20), nullable=False, default=UserRole.USER.value, index=True)

    # Account status
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"

    @property
    def is_admin(self) -> bool:
        """Check if user has admin role."""
        return self.role == UserRole.ADMIN.value
