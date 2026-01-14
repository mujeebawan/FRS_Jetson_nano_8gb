"""
Database models for Face Recognition Security System.
SQLAlchemy ORM models compatible with SQLite (dev) and PostgreSQL (prod).
"""

from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey,
    LargeBinary, Float, Boolean, Text, create_engine
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime, timezone
import uuid
import os


def local_now():
    """Get current local time (not UTC)."""
    return datetime.now()

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


class Person(Base):
    """
    Person model - stores enrolled individuals.
    Each person has a folder: data/persons/{uuid}/
    """
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    uuid = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, index=True)

    # Optional identification
    id_number = Column(String(50), unique=True, nullable=True, index=True)  # CNIC, passport, etc.

    # Person folder path (relative to data/persons/)
    folder_path = Column(String(500), nullable=True)

    # Primary reference image path
    reference_image_path = Column(String(500), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Watchlist/Criminal status
    watchlist_status = Column(String(50), default='normal', nullable=False, index=True)
    # Values: 'normal', 'criminal', 'most_wanted', 'suspect', 'person_of_interest', 'vip', 'banned'

    threat_level = Column(String(20), default='none', nullable=False, index=True)
    # Values: 'critical', 'high', 'medium', 'low', 'none'

    # Criminal/watchlist details
    criminal_notes = Column(Text, nullable=True)  # Why on watchlist
    added_to_watchlist_at = Column(DateTime, nullable=True)
    watchlist_expires_at = Column(DateTime, nullable=True)

    # Guard action prompt (shown when detected)
    guard_prompt = Column(Text, nullable=True)
    # e.g., "DETAIN IMMEDIATELY - Armed robbery suspect. Call police: 15"

    # Relationships
    embeddings = relationship("FaceEmbedding", back_populates="person", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="person")

    def __repr__(self):
        return f"<Person(id={self.id}, name='{self.name}', status='{self.watchlist_status}')>"


class FaceEmbedding(Base):
    """
    Face embedding model - stores 512-D face vectors.
    Multiple embeddings per person for robustness.
    """
    __tablename__ = "face_embeddings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=False, index=True)

    # 512-D embedding stored as binary blob
    embedding = Column(LargeBinary, nullable=False)

    # Source of embedding
    source = Column(String(50), nullable=False, default='original')
    # Values: 'original', 'augmented', 'video_frame'

    # Image this embedding was extracted from
    source_image_path = Column(String(500), nullable=True)

    # Detection confidence
    confidence = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship
    person = relationship("Person", back_populates="embeddings")

    def __repr__(self):
        return f"<FaceEmbedding(id={self.id}, person_id={self.person_id}, source='{self.source}')>"


class Alert(Base):
    """
    Alert model - security alerts when persons are detected.
    Snapshots organized: data/alerts/{YYYY-MM-DD}/alert_{id}_{HHMMSS}.jpg
    """
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=local_now, nullable=False, index=True)

    # Event type
    event_type = Column(String(50), nullable=False, index=True)
    # Values: 'criminal_detected', 'unknown_person', 'known_person', 'vip_detected', 'watchlist_match'

    # Person info (null for unknown)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=True, index=True)
    person_name = Column(String(255), nullable=True)  # Cached for quick display

    # Recognition details
    confidence = Column(Float, nullable=True)
    similarity_score = Column(Float, nullable=True)  # Cosine similarity

    # Snapshot path (date-wise folder)
    snapshot_path = Column(String(500), nullable=True)

    # Camera info (which camera detected the face)
    camera_id = Column(Integer, ForeignKey("cameras.id"), nullable=True)
    camera_name = Column(String(255), nullable=True)  # Cached for quick display

    # Cached threat info (denormalized from Person for fast queries)
    threat_level = Column(String(20), nullable=True, index=True)
    watchlist_status = Column(String(50), nullable=True, index=True)

    # Guard prompt displayed at time of alert
    displayed_prompt = Column(Text, nullable=True)

    # Guard verification
    guard_verified = Column(Boolean, default=False, nullable=False, index=True)
    guard_action = Column(String(50), nullable=True)
    # Values: 'confirmed', 'false_alarm', 'investigating', 'apprehended', 'escalated', 'ignored'
    guard_verified_by = Column(String(100), nullable=True)
    guard_verified_at = Column(DateTime, nullable=True)
    action_notes = Column(Text, nullable=True)

    # Admin acknowledgment
    acknowledged = Column(Boolean, default=False, nullable=False, index=True)
    acknowledged_by = Column(String(100), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)

    # Relationship
    person = relationship("Person", back_populates="alerts")

    def __repr__(self):
        return f"<Alert(id={self.id}, type='{self.event_type}', threat='{self.threat_level}')>"


class RecognitionLog(Base):
    """
    Recognition log - audit trail of all face detections.
    Used for analytics and debugging.
    """
    __tablename__ = "recognition_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=local_now, nullable=False, index=True)

    # Detection details
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=True, index=True)
    matched = Column(Boolean, nullable=False, default=False)
    confidence = Column(Float, nullable=False)
    similarity_score = Column(Float, nullable=True)

    # Processing info
    processing_time_ms = Column(Float, nullable=True)
    faces_in_frame = Column(Integer, default=1)

    # Camera source
    camera_source = Column(String(100), nullable=True)

    def __repr__(self):
        return f"<RecognitionLog(id={self.id}, matched={self.matched}, conf={self.confidence:.2f})>"


class SystemConfiguration(Base):
    """
    System configuration - runtime settings stored in DB.
    Allows changing settings without restart.
    """
    __tablename__ = "system_configuration"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    config_key = Column(String(100), unique=True, nullable=False, index=True)
    config_value = Column(Text, nullable=False)
    data_type = Column(String(50), nullable=False)  # 'float', 'int', 'bool', 'string', 'json'
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<SystemConfiguration(key='{self.config_key}', value='{self.config_value}')>"


class Camera(Base):
    """
    Camera model - stores camera configuration for multi-camera support.
    Supports Hikvision cameras with multiple stream qualities.

    Hikvision DS-2CD7A47EWD-XZS Stream Channels:
    - Channel 101 (main): 4K/1080p high quality
    - Channel 102 (sub): 720p medium quality
    - Channel 103 (third): 480p low quality (recommended for AI)
    """
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)  # "Front Gate", "Back Door"
    ip_address = Column(String(45), nullable=False)  # IPv4 or IPv6
    port = Column(Integer, default=554)  # RTSP port
    username = Column(String(100), nullable=False)
    password = Column(String(255), nullable=False)  # Should be encrypted in production

    # Stream quality selection
    # main = Channel 101 (4K/1080p), sub = Channel 102 (720p), third = Channel 103 (480p)
    stream_quality = Column(String(20), default="third")

    # Camera state
    enabled = Column(Boolean, default=True)  # Include in pipeline
    detection_enabled = Column(Boolean, default=True)  # Run face detection

    # Per-camera settings (nullable = use global settings)
    detection_confidence = Column(Float, nullable=True)  # Override global
    recognition_threshold = Column(Float, nullable=True)  # Override global
    frame_skip = Column(Integer, nullable=True)  # Override global

    # Runtime status (updated by stream service)
    is_online = Column(Boolean, default=False)
    last_seen = Column(DateTime, nullable=True)
    current_fps = Column(Float, nullable=True)
    error_message = Column(String(500), nullable=True)

    # Metadata
    location = Column(String(255), nullable=True)  # Physical location description
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Constants for stream quality options
    STREAM_CHANNELS = {
        "main": "Streaming/Channels/101",    # 4K/1080p
        "sub": "Streaming/Channels/102",     # 720p
        "third": "Streaming/Channels/103",   # 480p (recommended)
    }

    QUALITY_DESCRIPTIONS = {
        "main": "High (4K/1080p)",
        "sub": "Medium (720p)",
        "third": "Low (480p) - Recommended for AI",
    }

    @property
    def rtsp_url(self) -> str:
        """Generate RTSP URL for this camera."""
        from urllib.parse import quote
        channel = self.STREAM_CHANNELS.get(self.stream_quality, "Streaming/Channels/103")
        # URL encode password to handle special characters
        encoded_password = quote(self.password, safe='')
        return f"rtsp://{self.username}:{encoded_password}@{self.ip_address}:{self.port}/{channel}"

    @property
    def display_status(self) -> str:
        """Get human-readable status."""
        if not self.enabled:
            return "Disabled"
        if self.is_online:
            return "Online"
        return "Offline"

    def __repr__(self):
        return f"<Camera(id={self.id}, name='{self.name}', ip='{self.ip_address}', status='{self.display_status}')>"
