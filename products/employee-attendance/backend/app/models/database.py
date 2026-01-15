"""
Database models for Employee Attendance System.
SQLAlchemy ORM models compatible with SQLite (dev) and PostgreSQL (prod).
"""

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey,
    LargeBinary, Float, Boolean, Text, Time, Date, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime, date, time
import uuid

from ..config import settings

Base = declarative_base()

# Database URL from settings
DATABASE_URL = settings.database_url

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency for getting database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database tables."""
    Base.metadata.create_all(bind=engine)


class Department(Base):
    """Department model - organizational units."""
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    code = Column(String(20), unique=True, nullable=True)  # e.g., "IT", "HR"
    manager_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    employees = relationship("Employee", back_populates="department")

    def __repr__(self):
        return f"<Department(id={self.id}, name='{self.name}')>"


class Employee(Base):
    """
    Employee model - stores enrolled employees for attendance tracking.
    """
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    uuid = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))

    # Employee identification
    employee_id = Column(String(50), unique=True, nullable=False, index=True)  # e.g., "EMP001"
    name = Column(String(255), nullable=False, index=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)

    # Department
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True, index=True)
    position = Column(String(100), nullable=True)  # Job title

    # Shift timing
    shift_start = Column(Time, default=time(9, 0))  # Default 09:00
    shift_end = Column(Time, default=time(18, 0))   # Default 18:00

    # Face recognition
    reference_image_path = Column(String(500), nullable=True)
    folder_path = Column(String(500), nullable=True)

    # Status
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    join_date = Column(Date, default=date.today, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    department = relationship("Department", back_populates="employees")
    embeddings = relationship("FaceEmbedding", back_populates="employee", cascade="all, delete-orphan")
    attendance_logs = relationship("AttendanceLog", back_populates="employee", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Employee(id={self.id}, emp_id='{self.employee_id}', name='{self.name}')>"


class FaceEmbedding(Base):
    """
    Face embedding model - stores 512-D face vectors.
    Multiple embeddings per employee for robustness.
    """
    __tablename__ = "face_embeddings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)

    # 512-D embedding stored as binary blob
    embedding = Column(LargeBinary, nullable=False)

    # Source of embedding
    source = Column(String(50), nullable=False, default='original')
    source_image_path = Column(String(500), nullable=True)
    confidence = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship
    employee = relationship("Employee", back_populates="embeddings")

    def __repr__(self):
        return f"<FaceEmbedding(id={self.id}, employee_id={self.employee_id})>"


class AttendanceLog(Base):
    """
    Attendance log - tracks daily check-in and check-out.
    One record per employee per day.
    """
    __tablename__ = "attendance_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    date = Column(Date, default=date.today, nullable=False, index=True)

    # Check-in/out times
    check_in_time = Column(DateTime, nullable=True)
    check_out_time = Column(DateTime, nullable=True)

    # Snapshots
    check_in_snapshot = Column(String(500), nullable=True)
    check_out_snapshot = Column(String(500), nullable=True)

    # Camera that recorded
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=True)
    camera_name = Column(String(255), nullable=True)

    # Status calculated based on shift times
    status = Column(String(20), default='present', nullable=False, index=True)
    # Values: 'present', 'late', 'early_leave', 'half_day', 'absent'

    # Work hours calculation
    work_hours = Column(Float, nullable=True)  # Total hours worked
    overtime_hours = Column(Float, nullable=True)  # Hours beyond standard 8
    late_minutes = Column(Integer, nullable=True)  # Minutes late from shift start

    # Notes
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    employee = relationship("Employee", back_populates="attendance_logs")

    def __repr__(self):
        return f"<AttendanceLog(id={self.id}, emp={self.employee_id}, date={self.date}, status='{self.status}')>"


class User(Base):
    """
    User model for authentication.
    Supports role-based access control (admin/user).
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default='user', nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"


class Camera(Base):
    """
    Camera model - stores camera configuration for attendance capture.
    """
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    ip_address = Column(String(45), nullable=False)
    port = Column(Integer, default=554)
    username = Column(String(100), nullable=False)
    password = Column(String(255), nullable=False)
    stream_quality = Column(String(20), default="sub")
    enabled = Column(Boolean, default=True)
    detection_enabled = Column(Boolean, default=True)

    # Per-camera settings
    detection_confidence = Column(Float, nullable=True)
    recognition_threshold = Column(Float, nullable=True)
    frame_skip = Column(Integer, nullable=True)

    # Runtime status
    is_online = Column(Boolean, default=False)
    last_seen = Column(DateTime, nullable=True)
    current_fps = Column(Float, nullable=True)
    error_message = Column(String(500), nullable=True)

    # Metadata
    location = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    STREAM_CHANNELS = {
        "main": "Streaming/Channels/101",
        "sub": "Streaming/Channels/102",
        "third": "Streaming/Channels/103",
    }

    @property
    def rtsp_url(self) -> str:
        from urllib.parse import quote
        channel = self.STREAM_CHANNELS.get(self.stream_quality, "Streaming/Channels/102")
        encoded_password = quote(self.password, safe='')
        return f"rtsp://{self.username}:{encoded_password}@{self.ip_address}:{self.port}/{channel}"

    @property
    def display_status(self) -> str:
        if not self.enabled:
            return "Disabled"
        return "Online" if self.is_online else "Offline"

    def __repr__(self):
        return f"<Camera(id={self.id}, name='{self.name}', status='{self.display_status}')>"


class SystemConfiguration(Base):
    """System configuration - runtime settings stored in DB."""
    __tablename__ = "system_configuration"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    config_key = Column(String(100), unique=True, nullable=False, index=True)
    config_value = Column(Text, nullable=False)
    data_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<SystemConfiguration(key='{self.config_key}')>"
