"""
Application configuration.
Loads settings from environment variables.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from .env file"""

    # Camera Configuration
    camera_ip: str = "192.168.1.64"
    camera_username: str = "admin"
    camera_password: str = "Mujeeb@321"
    camera_rtsp_port: int = 554

    # Stream URLs (constructed from camera settings)
    @property
    def camera_main_stream(self) -> str:
        return f"rtsp://{self.camera_username}:{self.camera_password}@{self.camera_ip}:{self.camera_rtsp_port}/Streaming/Channels/101"

    @property
    def camera_sub_stream(self) -> str:
        return f"rtsp://{self.camera_username}:{self.camera_password}@{self.camera_ip}:{self.camera_rtsp_port}/Streaming/Channels/102"

    @property
    def camera_third_stream(self) -> str:
        """720p stream - recommended for AI processing"""
        return f"rtsp://{self.camera_username}:{self.camera_password}@{self.camera_ip}:{self.camera_rtsp_port}/Streaming/Channels/103"

    # Application Settings
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    debug: bool = True
    log_level: str = "INFO"

    # Database
    database_url: str = "sqlite:///./data/face_recognition.db"

    # Face Recognition Settings
    detection_confidence: float = 0.5
    recognition_threshold: float = 0.4

    # Processing Settings
    process_stream: str = "sub"  # main, sub, or third (sub=channel 102 for better quality)
    frame_skip: int = 2  # Process every Nth frame (2 = more frequent detection with GPU+FP16)
    max_faces: int = 5  # Max faces to process per frame

    # Motion-based processing (disabled by default - camera VMD not configured)
    enable_motion_trigger: bool = False
    motion_sensitivity: float = 0.3

    # Security
    secret_key: str = "change-this-in-production-use-openssl-rand-hex-32"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Data Paths
    models_dir: str = "data/models"
    images_dir: str = "data/images"
    embeddings_dir: str = "data/embeddings"
    snapshots_dir: str = "data/snapshots"

    # Alert Settings
    alert_cooldown_seconds: int = 10  # Reduced from 60s for faster testing
    alert_on_unknown: bool = False  # Only alert on known watchlist persons
    alert_on_known: bool = True
    alert_save_snapshot: bool = True

    # Reference images directory (enrolled person photos)
    reference_images_dir: str = "data/images"

    # Model Configuration (optimized for Jetson Orin Nano 8GB)
    # Model packs: buffalo_s (smaller/faster) or buffalo_l (larger/more accurate)
    # Detection uses SCRFD from the model pack
    # Recognition uses ArcFace from the model pack
    recognition_model: str = "buffalo_s"  # buffalo_s (88MB FP16) or buffalo_l (171MB FP16)
    use_fp16: bool = True  # FP16 models for faster GPU inference
    use_gpu: bool = True  # GPU enabled by default

    # FAISS Settings
    faiss_use_gpu: bool = False  # Start with CPU, upgrade later

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
