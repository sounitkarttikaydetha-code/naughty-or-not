"""
Branding configuration helper for Clearance Check.
Single source of truth loaded from config/branding.yaml.
"""

from pathlib import Path
from typing import Any, Dict
import yaml

BRANDING_YAML = Path(__file__).resolve().parent.parent.parent / "config" / "branding.yaml"

_defaults = {
    "app_name": "Clearance Check",
    "app_subtitle": "Sanctions, Export-Control & Aviation Screening",
    "main_title": "Sanction checK",
    "short_name": "ClearanceCheck",
    "version_label": "v1.1.0",
}


def load_branding() -> Dict[str, str]:
    if BRANDING_YAML.is_file():
        try:
            with open(BRANDING_YAML, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            return {**_defaults, **data}
        except Exception:
            pass
    return dict(_defaults)


_branding = load_branding()

APP_NAME: str = _branding["app_name"]
APP_SUBTITLE: str = _branding["app_subtitle"]
MAIN_TITLE: str = _branding["main_title"]
SHORT_NAME: str = _branding["short_name"]
VERSION_LABEL: str = _branding["version_label"]
CODENAME: str = "Naughty or not"

EASTER_EGG_SIGNATURE: str = (
    "You actually scrolled all the way down here? Gotcha. Now smile for the camera. 📸. "
    "The developer got bored, you got curious and now we're even. Now go screen something. 🕵️ "
    "— Naughty or not, a brainchild of Sounit Karttikay "
    "(and the blood, sweat and tokens of Antigravity and Opus, no AIs were sanctioned in the making of this tool)"
)
