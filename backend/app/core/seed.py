"""
Database seeding for initial admin user.
Creates admin user on first startup if no users exist.
"""

import os
import logging
from sqlalchemy.orm import Session

from ..models.database import User
from .security import get_password_hash

logger = logging.getLogger(__name__)

# Default admin credentials (override via environment variables)
DEFAULT_ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
DEFAULT_ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", None)


def seed_admin_user(db: Session) -> None:
    """
    Create default admin user if no users exist.

    This ensures there's always at least one admin account
    to access the system after initial deployment.
    """
    # Check if any users exist
    user_count = db.query(User).count()

    if user_count > 0:
        logger.info(f"Database has {user_count} user(s), skipping admin seed")
        return

    # Create admin user
    logger.info("No users found, creating default admin user...")

    admin_user = User(
        username=DEFAULT_ADMIN_USERNAME.lower(),
        email=DEFAULT_ADMIN_EMAIL,
        hashed_password=get_password_hash(DEFAULT_ADMIN_PASSWORD),
        role="admin",
        is_active=True
    )

    db.add(admin_user)
    db.commit()

    logger.info(f"Created admin user: {DEFAULT_ADMIN_USERNAME}")

    # Warn if using default password
    if DEFAULT_ADMIN_PASSWORD == "admin123":
        logger.warning("=" * 60)
        logger.warning("WARNING: Using default admin password!")
        logger.warning("Please change it immediately via the Settings page")
        logger.warning("or set ADMIN_PASSWORD environment variable")
        logger.warning("=" * 60)
