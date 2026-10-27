"""
Country Sanctions, Export Control & Regulatory Screening Engine (T11 Part J).
Performs offline multi-regime screening for countries against:
- US OFAC comprehensive & selective sanctions regimes
- UK FCDO sanctions regimes
- EU CFSP restrictive measures
- UN Security Council resolutions
- FATF High-Risk (Black) & Increased Monitoring (Grey) lists
- EU Air Safety ban lists & FAA IASA categories
- US EAR Country Groups & ITAR 22 CFR 126.1 prohibited destinations

Zero external network calls; logs searches to SQLite with mode='country'.
"""

from datetime import datetime, timezone
import logging
from pathlib import Path
import re
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple
import yaml

import getpass
import platform
from modules.reporting.logger import DB_PATH
from modules.fatf.client import FATFClient
from modules.aviation.client import AviationClient

logger = logging.getLogger(__name__)

REGIMES_YAML = Path(__file__).resolve().parent.parent.parent / "config" / "country_regimes.yaml"


class CountryEngine:
    def __init__(self, regimes_path: Optional[Path] = None):
        self.regimes_path = regimes_path or REGIMES_YAML
        self.regimes: Dict[str, Any] = self._load_regimes()
        self.fatf_client = FATFClient()
        self.aviation_client = AviationClient()

    def _load_regimes(self) -> Dict[str, Any]:
        if not self.regimes_path.is_file():
            logger.warning(f"Country regimes YAML not found at {self.regimes_path}")
            return {}
        try:
            with open(self.regimes_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                return data.get("regimes", {})
        except Exception as e:
            logger.error(f"Error loading country regimes: {e}")
            return {}

    def normalize_input(self, text: str) -> str:
        if not text:
            return ""
        return re.sub(r"[^\w\s]", "", text.strip().lower())

    def lookup_country(self, query: str) -> Optional[Dict[str, Any]]:
        """Look up country configuration by ISO code or alias."""
        if not query:
            return None
        q_norm = self.normalize_input(query)
        q_upper = query.strip().upper()

        # 1. Direct ISO-2 lookup
        if q_upper in self.regimes:
            return dict(self.regimes[q_upper], iso2=q_upper)

        # 2. Alias lookup
        for iso, data in self.regimes.items():
            aliases = [self.normalize_input(a) for a in data.get("aliases", [])]
            name_norm = self.normalize_input(data.get("country", ""))
            if q_norm == name_norm or q_norm in aliases:
                return dict(data, iso2=iso)

        return None

    def screen_country(self, query: str) -> Dict[str, Any]:
        """
        Execute full regulatory evaluation of a country name or code.
        Never makes external network calls.
        """
        t0 = time.time()
        c_data = self.lookup_country(query)
        country_name = c_data.get("country") if c_data else query.strip().title()
        iso2 = c_data.get("iso2", "—") if c_data else "—"
        flag = c_data.get("flag", "🌐") if c_data else "🌐"

        # 1. FATF Evaluation
        fatf_res = self.fatf_client.screen_country(country_name)
        fatf_tier = fatf_res.get("tier", "NO_MATCH")
        fatf_finding = fatf_res.get("finding", "CLEAR")
        fatf_note = fatf_res.get("note", "")

        # 2. Aviation Safety Evaluation
        banned_carriers = []
        try:
            for item in self.aviation_client.eu_data.get("annex_a", []) + self.aviation_client.eu_data.get("annex_b", []):
                state = item.get("state") or ""
                if country_name.lower() in state.lower() or state.lower() in country_name.lower():
                    banned_carriers.append(item.get("airline"))
        except Exception:
            pass

        # 3. Overall Determination
        risk_level = c_data.get("risk_level", "STANDARD") if c_data else "STANDARD"
        is_comprehensive = (risk_level == "HIGH")
        is_selective = (risk_level == "ELEVATED")

        if risk_level == "HIGH" or fatf_tier == "POTENTIAL_MATCH":
            overall_tier = "POTENTIAL_MATCH"
            banner_icon = "🔴"
            risk_label = "HIGH RISK — COMPREHENSIVE REGIMES ACTIVE"
        elif risk_level == "ELEVATED" or fatf_tier == "POSSIBLE_MATCH_REVIEW" or len(banned_carriers) > 0:
            overall_tier = "POSSIBLE_MATCH_REVIEW"
            banner_icon = "🟠"
            risk_label = "ELEVATED RISK — SELECTIVE SANCTIONS / MONITORING"
        else:
            overall_tier = "NO_MATCH"
            banner_icon = "✅"
            risk_label = "STANDARD RISK — NO COMPREHENSIVE SANCTIONS"

        elapsed_ms = (time.time() - t0) * 1000.0

        return {
            "query": query,
            "country": country_name,
            "iso2": iso2,
            "flag": flag,
            "overall_tier": overall_tier,
            "banner_text": f"{banner_icon} {risk_label}",
            "is_comprehensive": is_comprehensive,
            "is_selective": is_selective,
            "regimes_data": c_data or {},
            "fatf_tier": fatf_tier,
            "fatf_finding": fatf_finding,
            "fatf_note": fatf_note,
            "eu_banned_airlines_count": len(banned_carriers),
            "eu_banned_airlines": banned_carriers,
            "execution_time_ms": elapsed_ms,
        }


def log_country_search(
    country_query: str,
    finding: str,
    banner_text: str,
    report_file_name: str = "",
    execution_time_ms: float = 0.0,
    db_path: Optional[Path] = None,
) -> None:
    """Log country regulatory search to SQLite screening_logs with mode='country'."""
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        now = datetime.now(timezone.utc).isoformat()
        user = getpass.getuser()
        machine = platform.node()

        conn.execute(
            """
            INSERT INTO screening_logs (
                timestamp, windows_user, machine_name, mode, search_type, query_type, inputs,
                top_match, result, score, duration_ms, report_file_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now,
                user,
                machine,
                "country",
                "Country",
                "country",
                f'{{"country": "{country_query}"}}',
                country_query,
                finding,
                1.0 if finding == "POTENTIAL_MATCH" else (0.75 if finding == "POSSIBLE_MATCH_REVIEW" else 0.0),
                execution_time_ms,
                report_file_name,
            ),
        )
        conn.commit()
    finally:
        conn.close()
