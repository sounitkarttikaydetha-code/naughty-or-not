"""
UI display helpers and responsive status chip components for Naughty or not.
"""

from typing import Tuple

CHIP_DEFINITIONS = {
    "POTENTIAL_MATCH": ("🔴", "LIKELY", "chip-likely"),
    "LIKELY": ("🔴", "LIKELY", "chip-likely"),
    "POSSIBLE_MATCH_REVIEW": ("🟠", "POSSIBLE", "chip-possible"),
    "POSSIBLE": ("🟠", "POSSIBLE", "chip-possible"),
    "BELOW_THRESHOLD": ("ℹ️", "INFO", "chip-info"),
    "INFO": ("ℹ️", "INFO", "chip-info"),
    "NO_MATCH": ("✅", "CLEAR", "chip-clear"),
    "CLEAR": ("✅", "CLEAR", "chip-clear"),
    "NOT_CHECKED": ("⚪", "NOT CHECKED", "chip-not-checked"),
    "FAILED": ("⚪", "NOT CHECKED", "chip-not-checked"),
    "NOT_RUN": ("⚪", "NOT RUN", "chip-not-checked"),
    "SAFETY": ("✈️", "SAFETY", "chip-safety"),
    "EXPORT_CONTROL": ("📦", "EXPORT CONTROL", "chip-export"),
    "EAR_RESTRICTION": ("📦", "EXPORT CONTROL", "chip-export"),
    "SOUNDS_LIKE": ("🔊", "SOUNDS LIKE", "chip-possible"),
}


def get_chip_meta(tier_or_type: str) -> Tuple[str, str, str]:
    """Return (symbol, word, css_class) for a given tier or status code."""
    key = str(tier_or_type).strip().upper()
    return CHIP_DEFINITIONS.get(key, ("⚪", key.replace("_", " "), "chip-not-checked"))


def render_status_chip(tier_or_type: str) -> str:
    """
    Render HTML for accessible status chip with minimum width, distinct colour,
    symbol, and full English word for colour-blind users.
    """
    sym, word, css_cls = get_chip_meta(tier_or_type)
    return (
        f'<span class="status-chip {css_cls}" aria-label="{word}">'
        f'<span class="chip-sym">{sym}</span> <span class="chip-word">{word}</span>'
        f'</span>'
    )
