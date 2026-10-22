"""
Application settings manager for Naughty or not.
Persists configuration, display preferences, and window state in settings.json.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional
from modules.common.paths import get_settings_path

DISPLAY_SIZE_SCALES = {
    "Small": 0.90,
    "Medium": 1.00,
    "Large": 1.15,
    "Extra large": 1.30,
}


def load_settings() -> Dict[str, Any]:
    """Load settings from settings.json."""
    path = get_settings_path()
    if path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f) or {}
        except Exception:
            return {}
    return {}


def save_settings(data: Dict[str, Any]) -> None:
    """Save dictionary to settings.json atomically."""
    path = get_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(".tmp")
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        temp_path.replace(path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()


def get_setting(key: str, default: Any = None) -> Any:
    """Get single setting value."""
    return load_settings().get(key, default)


def set_setting(key: str, value: Any) -> None:
    """Set and persist a single setting value."""
    data = load_settings()
    data[key] = value
    save_settings(data)


def get_display_scale() -> float:
    """Return numeric scale factor corresponding to current Display size setting."""
    size_name = get_setting("display_size", "Medium")
    return DISPLAY_SIZE_SCALES.get(size_name, 1.00)
