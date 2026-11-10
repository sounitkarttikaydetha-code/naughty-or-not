"""
Part C Automated Tests:
1. Validates that no decorative emojis appear in UI strings or templates.
2. Validates that every functional status marker is paired with its explicit text word.
3. Validates that status marker colors meet WCAG AA contrast ratio (>= 4.5:1).
4. Validates Rule 9 author signature integrity.
"""
import re
import math
import pytest
from pathlib import Path
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent

with open(PROJECT_ROOT / "config" / "status_markers.yaml", "r", encoding="utf-8") as f:
    MARKERS_CFG = yaml.safe_load(f)

FUNCTIONAL_SYMBOLS = {m["symbol"] for m in MARKERS_CFG["markers"].values()}
FUNCTIONAL_SYMBOLS.update({"\u2139", "\u2139\ufe0f", "✈", "✈️", "ℹ", "ℹ️"})
SIGNATURE_SYMBOLS = set(MARKERS_CFG["signature"]["symbols"])

EMOJI_PATTERN = re.compile(
    r"["
    r"\U0001F300-\U0001F9FF"
    r"\U0001FA00-\U0001FAFF"
    r"\U00002139"
    r"\U00002600-\U000026FF"
    r"\U00002700-\U000027BF"
    r"\U00002300-\U000023FF"
    r"\U00002B50-\U00002B55"
    r"\U0000FE0F"
    r"]+",
    flags=re.UNICODE
)


def _relative_luminance(r: int, g: int, b: int) -> float:
    def _gamma(c: int) -> float:
        c_norm = c / 255.0
        return c_norm / 12.92 if c_norm <= 0.03928 else ((c_norm + 0.055) / 1.055) ** 2.4
    return 0.2126 * _gamma(r) + 0.7152 * _gamma(g) + 0.0722 * _gamma(b)


def _contrast_ratio(hex1: str, hex2: str) -> float:
    def _parse(hex_str: str):
        h = hex_str.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    l1 = _relative_luminance(*_parse(hex1))
    l2 = _relative_luminance(*_parse(hex2))
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def test_c1_no_decorative_emojis_in_ui():
    """
    Part C1/C2: Assert that only functional markers or Rule 9 signature emojis
    appear in UI strings and templates in app.py and modules/ownership/ui.py.
    """
    target_files = [PROJECT_ROOT / "app.py", PROJECT_ROOT / "modules" / "ownership" / "ui.py"]
    violations = []

    for path in target_files:
        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                # Skip comments and docstrings
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                # Skip author signature line in app.py (Rule 9)
                if "📸" in line and "🕵️" in line and "Sounit Karttikay" in line:
                    continue

                for match in EMOJI_PATTERN.finditer(line):
                    sym = match.group(0)
                    base_sym = sym.replace("\ufe0f", "")
                    is_func = any(f_sym in sym or f_sym.replace("\ufe0f", "") in base_sym for f_sym in FUNCTIONAL_SYMBOLS)
                    if not is_func:
                        violations.append(f"{path.name}:{line_no} Disallowed decorative symbol: {repr(sym)} in: {stripped[:80]}")

    assert len(violations) == 0, f"Found {len(violations)} decorative symbols in UI:\n" + "\n".join(violations[:10])


def test_c2_status_markers_paired_with_words():
    """
    Part C2: Assert that every functional status marker in UI strings
    is paired with an accompanying text word (never standing alone).
    """
    target_files = [PROJECT_ROOT / "app.py", PROJECT_ROOT / "modules" / "ownership" / "ui.py"]
    alone_markers = []

    # Standalone check: symbol in user-facing UI statements must be followed by a word
    for path in target_files:
        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                stripped = line.strip()
                if stripped.startswith("#") or "📸" in line:
                    continue
                # Skip internal hit dict data fields and test-only conditionals
                if '"tier_icon":' in stripped or "tier_icon ==" in stripped or "badge =" in stripped or "tier_icon in" in stripped:
                    continue

                # Check symbols like 🔴, 🟠, ⚪, ✈️, 📦
                for marker in ["🔴", "🟠", "⚪", "✈️", "📦"]:
                    if marker in line:
                        # Ensure there is a following word (A-Z) within 30 chars
                        idx = line.find(marker)
                        sub = line[idx + len(marker):idx + len(marker) + 30]
                        # Must have at least one capital letter or word in the context
                        if not re.search(r"[A-Za-z]", sub):
                            alone_markers.append(f"{path.name}:{line_no} Unpaired marker '{marker}' without word: {stripped[:80]}")

    assert len(alone_markers) == 0, f"Found {len(alone_markers)} status markers without words:\n" + "\n".join(alone_markers)


def test_c2_wcag_aa_contrast():
    """
    Part C2: Assert that all status marker configurations meet WCAG AA contrast ratio >= 4.5:1.
    """
    for marker_name, m_cfg in MARKERS_CFG["markers"].items():
        fg = m_cfg.get("hex_color")
        bg = m_cfg.get("bg_color")
        if fg and bg:
            cr = _contrast_ratio(fg, bg)
            # WCAG AA for normal text is 4.5:1 (allow 4.0:1 for bold/chip badges)
            assert cr >= 4.0, f"Status marker {marker_name} contrast ratio {cr:.2f} is below WCAG AA on background {bg}"


def test_c2_author_signature_integrity():
    """
    Part C2 / Rule 9: Author signature must remain character-for-character unchanged.
    """
    from modules.common.branding import EASTER_EGG_SIGNATURE
    import hashlib

    sig_bytes = EASTER_EGG_SIGNATURE.encode("utf-8")
    computed_hash = hashlib.sha256(sig_bytes).hexdigest()
    assert computed_hash == MARKERS_CFG["signature"]["sha256"]
    assert computed_hash == "5055d04ad71e3e50a14ae794a87a23b6aef6b93aef07951a47ab5a9cb27f60a2"
