"""
Persistent Settings Store for Face Recognition Security System.
Saves runtime settings to JSON file so they persist across restarts.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
from threading import Lock

logger = logging.getLogger(__name__)

# Default settings file location
DEFAULT_SETTINGS_FILE = "data/settings.json"

# Settings that can be persisted
PERSISTABLE_SETTINGS = {
    "detection_confidence": {"default": 0.5, "min": 0.1, "max": 1.0},
    "recognition_threshold": {"default": 0.4, "min": 0.1, "max": 1.0},
    "frame_skip": {"default": 1, "min": 1, "max": 10},  # Default 1 for low latency
    "enable_motion_trigger": {"default": False},
    "alert_cooldown_seconds": {"default": 10, "min": 1, "max": 300},
    "recognition_model": {"default": "buffalo_s"},
    "use_fp16": {"default": True},
    "alert_on_unknown": {"default": False},
    "alert_on_known": {"default": True},
}


class SettingsStore:
    """
    Thread-safe persistent settings store.
    Saves settings to JSON file and loads them on startup.
    """

    _instance: Optional["SettingsStore"] = None
    _lock = Lock()

    def __new__(cls, settings_file: str = None):
        """Singleton pattern - only one settings store instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, settings_file: str = None):
        """Initialize settings store."""
        if self._initialized:
            return

        self._settings_file = Path(settings_file or DEFAULT_SETTINGS_FILE)
        self._settings: Dict[str, Any] = {}
        self._file_lock = Lock()

        # Ensure data directory exists
        self._settings_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing settings
        self._load()
        self._initialized = True

        logger.info(f"SettingsStore initialized: {self._settings_file}")

    def _load(self) -> None:
        """Load settings from JSON file."""
        try:
            if self._settings_file.exists():
                with open(self._settings_file, "r") as f:
                    loaded = json.load(f)
                    # Validate and merge with defaults
                    for key, config in PERSISTABLE_SETTINGS.items():
                        if key in loaded:
                            # Validate value is within bounds
                            value = loaded[key]
                            if "min" in config and "max" in config:
                                if isinstance(value, (int, float)):
                                    value = max(config["min"], min(config["max"], value))
                            self._settings[key] = value
                        else:
                            self._settings[key] = config["default"]
                logger.info(f"Loaded {len(self._settings)} settings from {self._settings_file}")
            else:
                # Use defaults
                self._settings = {k: v["default"] for k, v in PERSISTABLE_SETTINGS.items()}
                # Save defaults to file
                self._save()
                logger.info("Created settings file with defaults")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid settings JSON: {e}. Using defaults.")
            self._settings = {k: v["default"] for k, v in PERSISTABLE_SETTINGS.items()}
        except Exception as e:
            logger.error(f"Failed to load settings: {e}. Using defaults.")
            self._settings = {k: v["default"] for k, v in PERSISTABLE_SETTINGS.items()}

    def _save(self) -> bool:
        """Save settings to JSON file."""
        try:
            with self._file_lock:
                with open(self._settings_file, "w") as f:
                    json.dump(self._settings, f, indent=2)
            logger.debug(f"Settings saved to {self._settings_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        """Get a setting value."""
        if key in self._settings:
            return self._settings[key]
        if key in PERSISTABLE_SETTINGS:
            return PERSISTABLE_SETTINGS[key]["default"]
        return default

    def set(self, key: str, value: Any, save: bool = True) -> bool:
        """
        Set a setting value.

        Args:
            key: Setting name
            value: Setting value
            save: If True, immediately persist to file

        Returns:
            True if setting was updated successfully
        """
        if key not in PERSISTABLE_SETTINGS:
            logger.warning(f"Unknown setting: {key}")
            return False

        config = PERSISTABLE_SETTINGS[key]

        # Validate numeric bounds
        if "min" in config and "max" in config:
            if isinstance(value, (int, float)):
                if value < config["min"] or value > config["max"]:
                    logger.warning(f"Setting {key}={value} out of range [{config['min']}, {config['max']}]")
                    return False

        self._settings[key] = value

        if save:
            return self._save()
        return True

    def update(self, settings: Dict[str, Any], save: bool = True) -> Dict[str, bool]:
        """
        Update multiple settings at once.

        Args:
            settings: Dictionary of setting key-value pairs
            save: If True, persist after all updates

        Returns:
            Dictionary mapping setting keys to success status
        """
        results = {}
        for key, value in settings.items():
            results[key] = self.set(key, value, save=False)

        if save:
            self._save()

        return results

    def get_all(self) -> Dict[str, Any]:
        """Get all current settings."""
        return self._settings.copy()

    def reset_to_defaults(self, save: bool = True) -> None:
        """Reset all settings to defaults."""
        self._settings = {k: v["default"] for k, v in PERSISTABLE_SETTINGS.items()}
        if save:
            self._save()
        logger.info("Settings reset to defaults")

    def get_with_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Get all settings with their metadata (min, max, default)."""
        result = {}
        for key, config in PERSISTABLE_SETTINGS.items():
            result[key] = {
                "value": self._settings.get(key, config["default"]),
                **config
            }
        return result


# Global instance getter
def get_settings_store(settings_file: str = None) -> SettingsStore:
    """Get the singleton settings store instance."""
    return SettingsStore(settings_file)
