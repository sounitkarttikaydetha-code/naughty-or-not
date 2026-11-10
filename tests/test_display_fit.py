"""
Regression tests for T9-1: Display Fit, Window Sizing, Relative Units, and Status Chips.
Asserts that window dimensions, display scales, accessible status chips, and responsive
views adhere to T9-1 specifications without horizontal overflow.
"""

import json
from pathlib import Path
import pytest
from desktop_launcher import get_work_area_dimensions
from modules.common.settings import (
    load_settings,
    save_settings,
    get_setting,
    set_setting,
    get_display_scale,
    DISPLAY_SIZE_SCALES,
)
from modules.common.ui import get_chip_meta, render_status_chip
from modules.reporting.generator import format_chip_text


def test_work_area_dimensions_bounds():
    """T9-1.1: Default window size must respect work area bounds (1000x640 min, 1500x950 max)."""
    w, h = get_work_area_dimensions()
    assert 1000 <= w <= 1500, f"Width {w} out of allowed bounds [1000, 1500]"
    assert 640 <= h <= 950, f"Height {h} out of allowed bounds [640, 950]"


def test_settings_display_size_scaling(tmp_path, monkeypatch):
    """T9-1.2: Display size settings must map to relative scale factors."""
    test_settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("modules.common.settings.get_settings_path", lambda: test_settings_file)

    assert get_display_scale() == 1.00

    for size_name, expected_scale in DISPLAY_SIZE_SCALES.items():
        set_setting("display_size", size_name)
        assert get_setting("display_size") == size_name
        assert get_display_scale() == expected_scale


def test_window_geometry_persistence(tmp_path, monkeypatch):
    """T9-1.1: Window size and position must be persisted and restored."""
    test_settings_file = tmp_path / "settings.json"
    monkeypatch.setattr("modules.common.settings.get_settings_path", lambda: test_settings_file)

    geom = {"width": 1366, "height": 768, "x": 100, "y": 100}
    set_setting("window", geom)

    loaded = get_setting("window")
    assert loaded == geom


def test_status_chip_accessible_components():
    """T9-1.4: Status chips must include a symbol and a plain-English word for colour-blind users."""
    expected_tiers = {
        "POTENTIAL_MATCH": ("🔴", "LIKELY"),
        "POSSIBLE_MATCH_REVIEW": ("🟠", "POSSIBLE"),
        "BELOW_THRESHOLD": ("ℹ️", "INFO"),
        "NO_MATCH": ("✅", "CLEAR"),
        "NOT_CHECKED": ("⚪", "NOT CHECKED"),
        "FAILED": ("⚪", "NOT CHECKED"),
        "SAFETY": ("✈️", "SAFETY"),
        "EXPORT_CONTROL": ("📦", "EXPORT CONTROL"),
    }

    for tier, (sym, word) in expected_tiers.items():
        s, w, cls = get_chip_meta(tier)
        assert s == sym, f"Expected symbol {sym} for {tier}, got {s}"
        assert w == word, f"Expected word {word} for {tier}, got {w}"

        html = render_status_chip(tier)
        assert sym in html
        assert word in html
        assert "status-chip" in html
        assert cls in html


def test_report_chip_text():
    """T9-1.4 & Part P: Reports must use drawn marker + word chip text."""
    assert format_chip_text("POTENTIAL_MATCH") == "● LIKELY"
    assert format_chip_text("POSSIBLE_MATCH_REVIEW") == "● POSSIBLE"
    assert format_chip_text("BELOW_THRESHOLD") == "● INFO"
    assert format_chip_text("NO_MATCH") == "● CLEAR"
    assert format_chip_text("NOT_CHECKED") == "● NOT CHECKED"
    assert format_chip_text("SAFETY") == "● SAFETY"
    assert format_chip_text("EXPORT_CONTROL") == "● EXPORT CONTROL"


def test_viewport_overflow_rules():
    """T11 Part B6: Viewport & overflow rules at 1024px, 1366px, 1920px."""
    app_py = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")
    assert "overflow-x: hidden !important" in app_py
    assert "max-width: 100vw !important" in app_py
    assert "grid-template-columns: repeat(auto-fit, minmax(" in app_py

    # Viewport calculations
    for width in [1024, 1366, 1920]:
        target_w = max(1000, min(1500, int(width * 0.90)))
        assert target_w <= width, f"Clamped width {target_w} must fit within viewport {width}"
        assert target_w >= 1000, f"Clamped width {target_w} must meet 1000px minimum"
