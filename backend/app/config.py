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
    process_stream: str = "third"  # main, sub, or third
    frame_skip: int = 2  # Process every Nth frame
    max_faces: int = 5  # Max faces to process per frame

    # Motion-based processing
    enable_motion_trigger: bool = True
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
    alert_cooldown_seconds: int = 60
    alert_on_unknown: bool = True
    alert_on_known: bool = True
    alert_save_snapshot: bool = True

    # Model Configuration (optimized for Jetson Orin Nano 8GB)
    # Using SCRFD_2.5G for detection and MobileFaceNet for recognition
    detection_model: str = "scrfd_2.5g_kps"
    recognition_model: str = "buffalo_s"  # Smaller than buffalo_l
    use_tensorrt: bool = False  # Enable after TensorRT installation

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
