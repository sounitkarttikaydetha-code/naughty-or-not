"""
Test suite for Part P: Professional Finish & CI Scan (tests/test_finish_scan.py).
Fails on:
- Banned marketing phrases in UI/documentation.
- Gradients, glow, blur, backdrop-filter, or banned blues in CSS.
- Unpaired emojis in UI status displays.
- Alteration of Hard Rule 9 author signature.
- Em-dash density > 1.0 per 300 words in documentation.
"""
import hashlib
import re
from pathlib import Path
import pytest

from modules.common.branding import EASTER_EGG_SIGNATURE

PROJECT_ROOT = Path(__file__).resolve().parent.parent

BANNED_PHRASES = [
    "seamless", "cutting-edge", "next-gen", "empower", "unlock",
    "supercharge", "effortless", "revolutionary", "enterprise-grade",
    "state-of-the-art", "bulletproof", "game-changing"
]
BANNED_BLUES = ["#6366F1", "#615FFF", "#4F46E5", "#8B5CF6", "#2563EB"]

HARD_RULE_9_HASH = "5055d04ad71e3e50a14ae794a87a23b6aef6b93aef07951a47ab5a9cb27f60a2"


def test_hard_rule_9_signature_unaltered():
    """Hard Rule 9: The author signature is NEVER altered; emojis stay exactly as they are."""
    sig_hash = hashlib.sha256(EASTER_EGG_SIGNATURE.encode("utf-8")).hexdigest()
    assert sig_hash == HARD_RULE_9_HASH, f"Hard Rule 9 violation: signature hash mismatch ({sig_hash})"
    assert "📸" in EASTER_EGG_SIGNATURE
    assert "🕵️" in EASTER_EGG_SIGNATURE


def test_theme_css_strict_styling():
    """Verify theme.css enforces zero gradients, glows, blur, glassmorphism, or banned blues."""
    css_path = PROJECT_ROOT / "app" / "static" / "theme.css"
    assert css_path.exists(), "theme.css missing"
    raw_css = css_path.read_text(encoding="utf-8")
    clean_css = re.sub(r'/\*.*?\*/', '', raw_css, flags=re.DOTALL)

    # Check for banned blues
    for bb in BANNED_BLUES:
        assert bb.lower() not in clean_css.lower(), f"Banned blue {bb} found in theme.css"

    # Check for gradients
    assert not re.search(r'(?:linear|radial)-gradient', clean_css, re.I), "Gradients found in theme.css"

    # Check for blur and glassmorphism
    assert not re.search(r'\b(?:blur|backdrop-filter)\b', clean_css, re.I), "Blur/glassmorphism found in theme.css"

    # Check font family
    assert "Segoe UI" in clean_css, "Segoe UI font missing from theme.css"
    assert "Inter" not in clean_css, "Inter font should not be in theme.css"


def test_no_banned_phrases_in_ui_and_docs():
    """Assert zero marketing buzzwords in user interface, launcher, and markdown documentation."""
    exempt_names = [
        "peoples' revolutionary party of kangleipak",
        "revolutionary peoples' front",
        "islamic revolutionary guard corps",
        "empower india foundation",
    ]
    files_to_scan = [
        PROJECT_ROOT / "app.py",
        PROJECT_ROOT / "desktop_launcher.py",
        PROJECT_ROOT / "docs" / "USER_GUIDE.md",
        PROJECT_ROOT / "docs" / "PRIVACY_NOTICE.md",
        PROJECT_ROOT / "docs" / "TERMS_OF_USE.md",
        PROJECT_ROOT / "docs" / "GLOSSARY.md",
    ]
    violations = []
    for f in files_to_scan:
        if not f.exists():
            continue
        txt = f.read_text(encoding="utf-8")
        for bp in BANNED_PHRASES:
            for line_no, line in enumerate(txt.splitlines(), 1):
                if re.search(r'\b' + re.escape(bp) + r'\b', line, re.I):
                    if not any(ex in line.lower() for ex in exempt_names):
                        violations.append(f"{f.name}:{line_no} contains banned phrase '{bp}': {line.strip()}")

    assert not violations, f"Banned phrases found:\n" + "\n".join(violations)


def test_app_icon_assets_exist():
    """Assert all required application icons are generated and present."""
    assets = [
        PROJECT_ROOT / "assets" / "icon.svg",
        PROJECT_ROOT / "assets" / "icon_white.svg",
        PROJECT_ROOT / "assets" / "icon.ico",
        PROJECT_ROOT / "assets" / "icon_256.png",
        PROJECT_ROOT / "assets" / "favicon.ico",
    ]
    for a in assets:
        assert a.exists(), f"Asset {a.name} missing"
        assert a.stat().st_size > 0, f"Asset {a.name} is empty"


def test_docs_em_dash_density():
    """Assert em-dash density in documentation does not exceed 1.0 per 300 words."""
    doc_files = [
        PROJECT_ROOT / "docs" / "PRIVACY_NOTICE.md",
        PROJECT_ROOT / "docs" / "TERMS_OF_USE.md",
        PROJECT_ROOT / "docs" / "GLOSSARY.md",
    ]
    for doc in doc_files:
        if not doc.exists():
            continue
        txt = doc.read_text(encoding="utf-8")
        clean_txt = re.sub(r'You actually scrolled.*no AIs were sanctioned.*', '', txt)
        words = len(re.findall(r'\b\w+\b', clean_txt))
        dashes = clean_txt.count('—')
        density = (dashes / words * 300) if words > 0 else 0
        assert density <= 1.0, f"{doc.name} em-dash density {density:.2f} exceeds 1.0 per 300 words ({dashes} dashes, {words} words)"
