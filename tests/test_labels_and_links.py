"""
Tests for T8-7: Threshold slider, labels, and verify links.
"""

from pathlib import Path
import re
import yaml
from modules.raw_search.engine import load_sources_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_slider_not_present_in_ui():
    """Verify that no st.slider or threshold slider is present in app.py screening UI."""
    app_path = PROJECT_ROOT / "app.py"
    with open(app_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "st.slider" not in content, "Found st.slider in app.py — must be removed"
    assert "Red = likely match · Amber = possible match · Grey list = shown for information" in content


def test_no_ofsi_as_list_label():
    """
    Verify that OFSI is not used as a list label or authority.
    The list must be labeled 'UK Sanctions List (FCDO)'.
    """
    sources_yaml = PROJECT_ROOT / "config" / "sources.yaml"
    with open(sources_yaml, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    for s in data.get("sources", []):
        authority = s.get("authority", "")
        assert "OFSI" not in authority, f"Found OFSI in authority for {s.get('id')}"

    app_path = PROJECT_ROOT / "app.py"
    with open(app_path, "r", encoding="utf-8") as f:
        app_code = f.read()

    # Friendly source names check
    assert '"uk_csl": "UK Sanctions List (FCDO)"' in app_code


def test_verify_links_domains_and_schema():
    """
    Verify all official list verification links match required schemas and domains.
    - UK Sanctions: search-uk-sanctions-list.service.gov.uk
    - US OFAC: sanctionssearch.ofac.treas.gov
    - US CSL: trade.gov
    - EU: sanctionsmap.eu
    - UN: main.un.org
    - FATF: fatf-gafi.org
    """
    sources_yaml = PROJECT_ROOT / "config" / "sources.yaml"
    with open(sources_yaml, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    sources = {s["id"]: s for s in data.get("sources", [])}

    assert sources["uk_csl"]["verify_url"] == "https://search-uk-sanctions-list.service.gov.uk/"
    assert sources["us_ofac"]["verify_url"] == "https://sanctionssearch.ofac.treas.gov/"
    assert "trade.gov" in sources["us_csl"]["verify_url"]
    assert sources["eu_csl"]["verify_url"] == "https://www.sanctionsmap.eu/"
    assert "main.un.org" in sources["un_csl"]["verify_url"]
    assert sources["fatf_jurisdictions"]["verify_url"] == "https://www.fatf-gafi.org/en/topics/high-risk-and-other-monitored-jurisdictions.html"

    # All verify_urls must use HTTPS
    for sid, s in sources.items():
        v_url = s.get("verify_url", "")
        assert v_url.startswith("https://"), f"Source {sid} verify_url must use HTTPS: {v_url}"


def test_below_threshold_explanatory_text():
    """
    Reports and UI must show:
    'Candidate matches below threshold are shown for information only. They are not matches.'
    """
    expected_text = "Candidate matches below threshold are shown for information only. They are not matches."

    app_path = PROJECT_ROOT / "app.py"
    with open(app_path, "r", encoding="utf-8") as f:
        assert expected_text in f.read(), "Missing explanatory text in app.py"

    gen_path = PROJECT_ROOT / "modules" / "reporting" / "generator.py"
    with open(gen_path, "r", encoding="utf-8") as f:
        assert expected_text in f.read(), "Missing explanatory text in reporting/generator.py"
