"""
User settings service for runtime configuration.
Stores settings in a JSON file for persistence across restarts.
"""
import json
import os
from pathlib import Path
from typing import Optional

# Settings file location (in backend directory)
SETTINGS_FILE = Path(__file__).parent.parent.parent / "user_settings.json"

# Default settings
DEFAULT_SETTINGS = {
    "cookies_from_browser": "chrome",  # chrome, firefox, safari, edge, brave, etc.
    "whisper_model": "turbo",  # Model name (varies by backend: mlx vs faster-whisper)
}

# Valid browser options for cookie extraction
VALID_BROWSERS = ["chrome", "firefox", "safari", "edge", "opera", "brave", "chromium", "vivaldi"]


def _load_settings() -> dict:
    """Load settings from file, creating with defaults if doesn't exist."""
    if not SETTINGS_FILE.exists():
        _save_settings(DEFAULT_SETTINGS)
        return DEFAULT_SETTINGS.copy()

    try:
        with open(SETTINGS_FILE, "r") as f:
            settings = json.load(f)
            # Merge with defaults in case new settings are added
            return {**DEFAULT_SETTINGS, **settings}
    except (json.JSONDecodeError, IOError):
        return DEFAULT_SETTINGS.copy()


def _save_settings(settings: dict) -> None:
    """Save settings to file."""
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=2)


def get_cookies_browser() -> str:
    """Get the browser to use for cookie extraction."""
    settings = _load_settings()
    browser = settings.get("cookies_from_browser", "chrome")
    return browser if browser in VALID_BROWSERS else "chrome"


def set_cookies_browser(browser: str) -> bool:
    """Set the browser for cookie extraction. Returns True if valid."""
    if browser not in VALID_BROWSERS:
        return False

    settings = _load_settings()
    settings["cookies_from_browser"] = browser
    _save_settings(settings)
    return True


def get_all_settings() -> dict:
    """Get all user settings."""
    return _load_settings()


def get_valid_browsers() -> list[str]:
    """Get list of valid browser options."""
    return VALID_BROWSERS.copy()


def get_whisper_model() -> str:
    """Get the selected Whisper model."""
    settings = _load_settings()
    return settings.get("whisper_model", "turbo")


def set_whisper_model(model: str) -> bool:
    """Set the Whisper model. Returns True on success."""
    settings = _load_settings()
    settings["whisper_model"] = model
    _save_settings(settings)
    return True
