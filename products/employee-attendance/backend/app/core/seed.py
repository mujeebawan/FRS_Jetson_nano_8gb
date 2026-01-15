"""
Database seeding for Employee Attendance System.
Creates admin user and default departments on first startup.
"""

import os
import logging
from sqlalchemy.orm import Session

from ..models.database import User, Department
from .security import get_password_hash

logger = logging.getLogger(__name__)

# Default admin credentials (override via environment variables)
DEFAULT_ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
DEFAULT_ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", None)

# Default departments
DEFAULT_DEPARTMENTS = [
    {"name": "Human Resources", "code": "HR"},
    {"name": "Information Technology", "code": "IT"},
    {"name": "Engineering", "code": "ENG"},
    {"name": "Sales", "code": "SALES"},
    {"name": "Operations", "code": "OPS"},
    {"name": "Administration", "code": "ADMIN"},
    {"name": "Finance", "code": "FIN"},
    {"name": "Marketing", "code": "MKT"},
]


def seed_admin_user(db: Session) -> None:
    """Create default admin user if no users exist."""
    user_count = db.query(User).count()

    if user_count > 0:
        logger.info(f"Database has {user_count} user(s), skipping admin seed")
        return

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

    if DEFAULT_ADMIN_PASSWORD == "admin123":
        logger.warning("=" * 60)
        logger.warning("WARNING: Using default admin password!")
        logger.warning("Please change it immediately via the Settings page")
        logger.warning("=" * 60)


def seed_departments(db: Session) -> None:
    """Create default departments if none exist."""
    dept_count = db.query(Department).count()

    if dept_count > 0:
        logger.info(f"Database has {dept_count} department(s), skipping department seed")
        return

    logger.info("No departments found, creating default departments...")

    for dept_data in DEFAULT_DEPARTMENTS:
        dept = Department(
            name=dept_data["name"],
            code=dept_data["code"]
        )
        db.add(dept)

    db.commit()
    logger.info(f"Created {len(DEFAULT_DEPARTMENTS)} default departments")


def seed_database(db: Session) -> None:
    """Run all seed functions."""
    seed_admin_user(db)
    seed_departments(db)
