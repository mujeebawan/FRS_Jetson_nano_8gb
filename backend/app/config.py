"""
Application configuration.
Loads settings from environment variables and persistent storage.

Priority (highest to lowest):
1. Environment variables / .env file
2. Persisted settings (data/settings.json)
3. Default values
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional
import json
from pathlib import Path


def _load_persisted_settings() -> dict:
    """Load persisted settings from JSON file."""
    # Use absolute path relative to project root (parent of backend dir)
    project_root = Path(__file__).parent.parent.parent
    settings_file = project_root / "data" / "settings.json"
    if settings_file.exists():
        try:
            with open(settings_file, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


# Load persisted settings once at module load
_persisted = _load_persisted_settings()


class Settings(BaseSettings):
    """Application settings loaded from .env file and persistent storage"""

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

    # Face Recognition Settings (with persistent defaults)
    detection_confidence: float = _persisted.get("detection_confidence", 0.5)
    recognition_threshold: float = _persisted.get("recognition_threshold", 0.4)

    # Processing Settings (with persistent defaults)
    process_stream: str = "sub"  # main, sub, or third (sub=channel 102 for better quality)
    frame_skip: int = _persisted.get("frame_skip", 1)  # Default 1 for lowest latency
    max_faces: int = 5  # Max faces to process per frame

    # Motion-based processing (disabled by default - camera VMD not configured)
    enable_motion_trigger: bool = _persisted.get("enable_motion_trigger", False)
    motion_sensitivity: float = 0.3

    # Security
    secret_key: str = "change-this-in-production-use-openssl-rand-hex-32"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Data Paths (absolute, relative to project root)
    @property
    def _project_root(self) -> Path:
        return Path(__file__).parent.parent.parent

    @property
    def models_dir(self) -> str:
        return str(self._project_root / "data" / "models")

    @property
    def images_dir(self) -> str:
        return str(self._project_root / "data" / "images")

    @property
    def embeddings_dir(self) -> str:
        return str(self._project_root / "data" / "embeddings")

    @property
    def snapshots_dir(self) -> str:
        """Alert snapshots directory - now unified under alerts folder."""
        return str(self._project_root / "data" / "alerts")

    @property
    def alerts_data_dir(self) -> str:
        """Unified alerts data directory for snapshots and video clips."""
        return str(self._project_root / "data" / "alerts")

    # Alert Settings (with persistent defaults)
    alert_cooldown_seconds: int = _persisted.get("alert_cooldown_seconds", 10)
    alert_on_unknown: bool = _persisted.get("alert_on_unknown", False)
    alert_on_known: bool = _persisted.get("alert_on_known", True)
    alert_save_snapshot: bool = True

    # Video Recording Settings (with persistent defaults)
    video_recording_enabled: bool = _persisted.get("video_recording_enabled", True)
    video_clip_duration: int = _persisted.get("video_clip_duration", 5)  # seconds before+after (3-10)

    @property
    def clips_dir(self) -> str:
        """Video clips directory - unified under alerts folder."""
        return str(self._project_root / "data" / "alerts")

    # Reference images directory (enrolled person photos)
    @property
    def reference_images_dir(self) -> str:
        return str(self._project_root / "data" / "images")

    # Model Configuration (with persistent defaults)
    recognition_model: str = _persisted.get("recognition_model", "buffalo_s")
    use_fp16: bool = _persisted.get("use_fp16", True)
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
