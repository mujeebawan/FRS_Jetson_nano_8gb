"""
Database seeding utilities.
Seeds the admin user on application startup.
"""

import os
import logging
from sqlalchemy.orm import Session

from ..models import User, UserRole
from .security import get_password_hash

logger = logging.getLogger(__name__)

# Default admin credentials from environment
DEFAULT_ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
DEFAULT_ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@frs.local")


def seed_admin_user(db: Session) -> bool:
    """
    Seed the admin user if no admin exists.

    Reads credentials from environment variables:
    - ADMIN_USERNAME (default: admin)
    - ADMIN_PASSWORD (default: admin123)
    - ADMIN_EMAIL (default: admin@frs.local)

    Returns:
        True if admin was created, False if already exists
    """
    # Check if any admin user exists
    existing_admin = db.query(User).filter(User.role == UserRole.ADMIN.value).first()

    if existing_admin:
        logger.info(f"Admin user already exists: {existing_admin.username}")
        return False

    # Create admin user
    admin_user = User(
        username=DEFAULT_ADMIN_USERNAME,
        email=DEFAULT_ADMIN_EMAIL,
        hashed_password=get_password_hash(DEFAULT_ADMIN_PASSWORD),
        role=UserRole.ADMIN.value,
        is_active=True
    )

    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)

    logger.info(f"Admin user created: {admin_user.username}")

    # Warn if using default password
    if DEFAULT_ADMIN_PASSWORD == "admin123":
        logger.warning(
            "⚠️  Admin user created with DEFAULT password! "
            "Set ADMIN_PASSWORD environment variable for production."
        )

    return True


def run_seed(db: Session):
    """
    Run all database seeds.

    Called on application startup.
    """
    logger.info("Running database seeds...")
    seed_admin_user(db)
    logger.info("Database seeding complete.")
