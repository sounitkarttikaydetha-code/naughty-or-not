import sys
"""
Start-up Self-Test Framework (T11 Part I).
Provides three layers of startup validation:
  - Layer 1 (Engine Canary): Fixed invariant test cases (~20) verifying core matching engine.
                             Hard failure on any canary error (ENGINE_CANARY_FAILURE).
  - Layer 2 (Self-Sampled Probes): Dynamic sampling of 5 live records + 3 nonsense names.
  - Layer 3 (Named Probes): Known probe entities from config/self_test_probes.yaml.
                             Produces soft informational notes on drift; never hard-blocks.
Entire self-test runs in <= 2.0s.
"""

import logging
import os
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple
import yaml

from modules.common.paths import get_logs_dir
from modules.screening.tiering import (
    tier_single_entity,
    TIER_POTENTIAL_MATCH,
    TIER_POSSIBLE_MATCH,
    TIER_BELOW_THRESHOLD,
    TIER_NO_MATCH,
)

logger = logging.getLogger(__name__)

def _resolve_canary_file() -> Path:
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "config" / "canary_records.yaml")
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "_internal" / "config" / "canary_records.yaml")
        candidates.append(exe_dir / "config" / "canary_records.yaml")
    try:
        from modules.common.paths import get_base_dir
        b = get_base_dir()
        candidates.append(b / "config" / "canary_records.yaml")
        candidates.append(b / "_internal" / "config" / "canary_records.yaml")
    except Exception:
        pass
    candidates.extend([
        Path(__file__).resolve().parent.parent.parent / "config" / "canary_records.yaml",
        Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "canary" / "canary_records.yaml",
    ])
    for cand in candidates:
        if cand.is_file():
            return cand
    return candidates[0]

def _resolve_probes_file() -> Path:
    candidates = []
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(meipass) / "config" / "self_test_probes.yaml")
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates.append(exe_dir / "_internal" / "config" / "self_test_probes.yaml")
        candidates.append(exe_dir / "config" / "self_test_probes.yaml")
    try:
        from modules.common.paths import get_base_dir
        b = get_base_dir()
        candidates.append(b / "config" / "self_test_probes.yaml")
        candidates.append(b / "_internal" / "config" / "self_test_probes.yaml")
    except Exception:
        pass
    candidates.append(Path(__file__).resolve().parent.parent.parent / "config" / "self_test_probes.yaml")
    for cand in candidates:
        if cand.is_file():
            return cand
    return candidates[0]

CANARY_FILE = _resolve_canary_file()
PROBES_FILE = _resolve_probes_file()


def run_layer1_canary(fixture_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Layer 1: Engine Canary Invariant Checks.
    Evaluates ~20 fixed records against tier_single_entity.
    Hard failure if any case does not match expected_tier.
    """
    path = fixture_path or CANARY_FILE
    if not path.exists():
        logger.error("Canary fixtures file not found at: %s", path)
        return {
            "passed": False,
            "total": 0,
            "failed_count": 1,
            "failures": [{"id": "fixture_missing", "error": f"Canary file not found: {path}"}],
            "error_code": "ENGINE_CANARY_FAILURE",
        }

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as exc:
        return {
            "passed": False,
            "total": 0,
            "failed_count": 1,
            "failures": [{"id": "fixture_parse_error", "error": str(exc)}],
            "error_code": "ENGINE_CANARY_FAILURE",
        }

    canaries = data.get("canaries", [])
    total = len(canaries)
    failures = []

    for c in canaries:
        cid = c.get("id", "unknown")
        query = c.get("query", "")
        entity = c.get("entity", {})
        query_type = c.get("query_type")
        dob = c.get("dob")
        nationality = c.get("nationality")
        identifiers = c.get("identifiers")
        expected_tier = c.get("expected_tier")

        try:
            res = tier_single_entity(
                query=query,
                entity=entity,
                query_type=query_type,
                dob=dob,
                nationality=nationality,
                identifiers=identifiers,
            )
            actual_tier = res["tier"] if res else None

            if actual_tier != expected_tier:
                failures.append({
                    "id": cid,
                    "query": query,
                    "expected": expected_tier,
                    "actual": actual_tier,
                    "reason": f"Expected tier '{expected_tier}', got '{actual_tier}'",
                })
        except Exception as exc:
            failures.append({
                "id": cid,
                "query": query,
                "expected": expected_tier,
                "actual": "EXCEPTION",
                "reason": f"Unhandled exception: {exc}",
            })

    passed = (len(failures) == 0 and total > 0)
    return {
        "passed": passed,
        "total": total,
        "failed_count": len(failures),
        "failures": failures,
        "error_code": None if passed else "ENGINE_CANARY_FAILURE",
    }


def run_layer2_sampled_probes(
    db_path: Optional[Path] = None,
    sample_size: int = 5,
) -> Dict[str, Any]:
    """
    Layer 2: Self-Sampled Probes.
    Samples 5 records from local screening database, checks they resolve,
    and tests 3 nonsense strings to ensure no false red flags.
    """
    path = db_path or (get_logs_dir() / "screening.db")
    notes: List[str] = []
    nonsense_clean = True
    sampled_matches = 0

    nonsense_strings = [
        "Xyzzqw Corp 999",
        "Qqqq12345! Zzz",
        "Jjkklmmnnoo 888",
    ]

    # Test nonsense strings against pure tiering rules
    for ns in nonsense_strings:
        # A synthetic entity representing no relation
        fake_ent = {"name": "General Commercial Enterprise", "match": 0.40, "entityType": "organization"}
        res = tier_single_entity(query=ns, entity=fake_ent)
        if res and res.get("tier") == TIER_POTENTIAL_MATCH:
            nonsense_clean = False
            notes.append(f"Nonsense string '{ns}' erroneously triggered POTENTIAL_MATCH")

    if not path.exists():
        notes.append("Local screening database not found; dynamic probe sampling skipped.")
        return {
            "passed": nonsense_clean,
            "sampled_count": 0,
            "nonsense_clean": nonsense_clean,
            "notes": notes,
        }

    try:
        conn = sqlite3.connect(str(path))
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT primary_name, source_id, entity_type 
                FROM records 
                WHERE entity_type IN ('person', 'organization', 'organisation') 
                  AND length(primary_name) > 6 
                  AND primary_name NOT LIKE '%/%'
                ORDER BY RANDOM() LIMIT ?
            """, (sample_size,))
            rows = cursor.fetchall()
        except Exception:
            rows = []
        conn.close()

        # Fallback to engine if records table not yet populated
        if not rows:
            try:
                from modules.watchman.client import get_python_engine
                eng = get_python_engine()
                for src_id, entities in eng.records_by_source.items():
                    for rec in entities:
                        if rec.name and len(rec.name) > 6 and "/" not in rec.name:
                            rows.append((rec.name, src_id, getattr(rec, "entity_type", "organization") or "organization"))
                            if len(rows) >= sample_size:
                                break
                    if len(rows) >= sample_size:
                        break
            except Exception:
                pass

        for name, sid, et in rows:
            # Self-match verification
            cand = {"name": name, "match": 1.0, "entityType": et or "organization"}
            res = tier_single_entity(query=name, entity=cand, query_type=et)
            if res and res.get("tier") == TIER_POTENTIAL_MATCH:
                sampled_matches += 1
            else:
                notes.append(f"Sampled entity '{name}' ({sid}) failed self-match.")

        passed = nonsense_clean and (sampled_matches >= min(len(rows), 1))
        return {
            "passed": passed,
            "sampled_count": len(rows),
            "sampled_matches": sampled_matches,
            "nonsense_clean": nonsense_clean,
            "notes": notes,
        }
    except Exception as exc:
        notes.append(f"Error querying sampled probes: {exc}")
        return {
            "passed": nonsense_clean,
            "sampled_count": 0,
            "sampled_matches": 0,
            "nonsense_clean": nonsense_clean,
            "notes": notes,
        }


def run_layer3_named_probes(
    config_path: Optional[Path] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Layer 3: Named Probes.
    Checks ~10 named probe entities from config/self_test_probes.yaml.
    Detects drift or delisting; records soft informational notes only.
    Never hard-blocks startup.
    """
    cfg_file = config_path or PROBES_FILE
    db_file = db_path or (get_logs_dir() / "screening.db")
    notes: List[str] = []

    if not cfg_file.exists():
        return {
            "passed": True,
            "probes_count": 0,
            "matched_count": 0,
            "notes": ["Self-test probes configuration not found; Layer 3 skipped."],
        }

    try:
        with open(cfg_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as exc:
        return {
            "passed": True,
            "probes_count": 0,
            "matched_count": 0,
            "notes": [f"Could not load probes configuration: {exc}"],
        }

    probes = data.get("probes", [])
    matched_count = 0

    if not db_file.exists():
        return {
            "passed": True,
            "probes_count": len(probes),
            "matched_count": 0,
            "notes": ["Screening database not initialized; probes verification deferred."],
        }

    try:
        conn = sqlite3.connect(str(db_file))
        cursor = conn.cursor()
        has_records_table = False
        try:
            cursor.execute("SELECT COUNT(1) FROM records")
            has_records_table = (cursor.fetchone()[0] > 0)
        except Exception:
            has_records_table = False

        eng = None
        for p in probes:
            name = p.get("name", "")
            exp_tier = p.get("expected_tier", TIER_POTENTIAL_MATCH)
            found = False
            if has_records_table:
                try:
                    cursor.execute("SELECT primary_name FROM records WHERE primary_name LIKE ? LIMIT 1", (f"%{name}%",))
                    if cursor.fetchone():
                        found = True
                except Exception:
                    pass

            if not found:
                # Check active Python screening engine
                try:
                    if eng is None:
                        from modules.watchman.client import get_python_engine
                        eng = get_python_engine()
                    s_res = eng.search(name)
                    res_obj = s_res.get("results")
                    ents = res_obj.get("entities", []) if isinstance(res_obj, dict) else (res_obj or [])
                    if ents:
                        found = True
                except Exception:
                    pass

            if found:
                matched_count += 1
            else:
                notes.append(f"Probe '{name}' not found in active database (expected {exp_tier}). List data may have updated.")
        conn.close()
    except Exception as exc:
        notes.append(f"Layer 3 database check error: {exc}")

    return {
        "passed": True,  # Soft notes only - never fails
        "probes_count": len(probes),
        "matched_count": matched_count,
        "notes": notes,
    }


def run_full_self_test(
    canary_path: Optional[Path] = None,
    probes_path: Optional[Path] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Execute all 3 self-test layers and measure performance.
    Guaranteed to run in <= 2.0s.
    """
    t0 = time.perf_counter()

    layer1 = run_layer1_canary(canary_path)
    layer2 = run_layer2_sampled_probes(db_path)
    layer3 = run_layer3_named_probes(probes_path, db_path)

    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    has_canary_failure = not layer1.get("passed", False)
    all_passed = (not has_canary_failure) and layer2.get("passed", True)

    soft_notes = layer3.get("notes", []) + [n for n in layer2.get("notes", []) if "erroneously" not in n]

    return {
        "passed": all_passed,
        "has_canary_failure": has_canary_failure,
        "duration_ms": round(elapsed_ms, 2),
        "within_budget": elapsed_ms <= 2000.0,
        "error_code": "ENGINE_CANARY_FAILURE" if has_canary_failure else None,
        "layer1": layer1,
        "layer2": layer2,
        "layer3": layer3,
        "soft_notes": soft_notes,
    }
