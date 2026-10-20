"""
OpenSanctions API Client (optional, uses credits)
Screens entities against the hosted OpenSanctions API with strict credit guards,
automatic usage logging, schema mapping, and tier assignment.
"""

import csv
import datetime
import getpass
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.parse
import urllib.request

from modules.screening.config import (
    CANDIDATE_MIN_MATCH,
    POSSIBLE_MATCH_THRESHOLD,
    POTENTIAL_MATCH_THRESHOLD,
)

logger = logging.getLogger(__name__)

# Constants
TIER_POTENTIAL_MATCH = "POTENTIAL_MATCH"            # 🔴
TIER_POSSIBLE_MATCH = "POSSIBLE_MATCH_REVIEW"       # 🟠
TIER_NO_MATCH = "NO_MATCH"                          # ✅
TIER_NOT_CHECKED = "NOT_CHECKED"                    # ⚪

STATUS_DISABLED = "DISABLED"
STATUS_NOT_RUN = "NOT_RUN"
STATUS_OK = "OK"
STATUS_UNAVAILABLE = "UNAVAILABLE"
STATUS_ERROR = "ERROR"

DEFAULT_API_URL = "https://api.opensanctions.org"
DEFAULT_DATASET = "sanctions"

USAGE_LOG_PATH = Path("logs/opensanctions_usage.csv")


def get_api_key() -> Optional[str]:
    """Retrieve OPENSANCTIONS_API_KEY from environment or .env file."""
    key = os.getenv("OPENSANCTIONS_API_KEY")
    if key and key.strip():
        return key.strip()

    # Fallback: parse .env directly if present
    env_paths = [Path(".env"), Path(__file__).resolve().parents[2] / ".env"]
    for env_path in env_paths:
        if env_path.exists():
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        if k.strip() == "OPENSANCTIONS_API_KEY":
                            val = v.strip().strip('"').strip("'")
                            if val:
                                return val
    return None


def map_schema(search_type: Optional[str]) -> str:
    """Map internal screening types to FollowTheMoney schemas."""
    if not search_type:
        return "Company"

    st = search_type.strip().lower()
    if st in ["person", "individual"]:
        return "Person"
    elif st in ["airline"]:
        return "Company"
    elif st in ["aircraft", "airplane"]:
        return "Airplane"
    elif st in ["vessel", "ship"]:
        return "Vessel"
    elif st in ["organisation", "organization", "company", "business"]:
        return "Company"
    return "Company"


def log_usage(
    query: str,
    schema: str,
    credits_consumed: int,
    http_status: int,
    user: Optional[str] = None,
) -> None:
    """Append a screening transaction to logs/opensanctions_usage.csv."""
    USAGE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    file_exists = USAGE_LOG_PATH.exists()

    username = user or getpass.getuser()
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    with open(USAGE_LOG_PATH, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "timestamp",
                "user",
                "query",
                "schema",
                "credits_consumed",
                "http_status",
            ])
        writer.writerow([
            timestamp,
            username,
            query,
            schema,
            credits_consumed,
            http_status,
        ])


def credits_used() -> Dict[str, int]:
    """Read logs/opensanctions_usage.csv and compute total credits consumed."""
    if not USAGE_LOG_PATH.exists():
        return {"total_credits": 0, "total_calls": 0}

    total_credits = 0
    total_calls = 0

    with open(USAGE_LOG_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_calls += 1
            try:
                total_credits += int(row.get("credits_consumed", 0))
            except (ValueError, TypeError):
                total_credits += 1

    return {"total_credits": total_credits, "total_calls": total_calls}


class OpenSanctionsClient:
    """Client for screening entities via the OpenSanctions Hosted API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_API_URL,
        dataset: str = DEFAULT_DATASET,
        timeout: float = 10.0,
    ):
        if api_key is None:
            self.api_key = get_api_key()
        else:
            self.api_key = api_key.strip() if api_key else ""
        self.base_url = base_url.rstrip("/")
        self.dataset = dataset
        self.timeout = float(timeout)

    def is_configured(self) -> bool:
        """Check if a valid API key is present."""
        return bool(self.api_key and self.api_key.strip())

    def match(
        self,
        name: str,
        search_type: Optional[str] = "Company",
        use_opensanctions: bool = False,
        dob: Optional[str] = None,
        yob: Optional[str] = None,
        nationality: Optional[str] = None,
        country: Optional[str] = None,
        id_number: Optional[str] = None,
        imo: Optional[str] = None,
        registration: Optional[str] = None,
        **extra_fields: Any,
    ) -> Dict[str, Any]:
        """
        Screen an entity against OpenSanctions via /match/<dataset>.

        :param name: Primary query name
        :param search_type: Person / Organisation / Airline / Aircraft / Vessel
        :param use_opensanctions: Mandatory credit guard. Must be explicitly True.
        :param dob: Date of birth (YYYY-MM-DD)
        :param yob: Year of birth
        :param nationality: Country of nationality
        :param country: Country of registration/residence
        :param id_number: National ID or Passport number
        :param imo: Vessel IMO number
        :param registration: Aircraft registration / tail number
        :return: Clean dict with status, tier, best_hit, hits, and credits consumed
        """
        # 1. Credit Guard: strictly require use_opensanctions=True
        if not use_opensanctions:
            return {
                "status": STATUS_NOT_RUN,
                "tier": TIER_NOT_CHECKED,
                "reason": "credit_guard_off",
                "message": "OpenSanctions screening was not requested (use_opensanctions=False)",
                "credits_consumed": 0,
                "best_hit": None,
                "hits": [],
            }

        # 2. Check if API Key is configured
        if not self.is_configured():
            return {
                "status": STATUS_DISABLED,
                "tier": TIER_NOT_CHECKED,
                "reason": "missing_api_key",
                "message": "OPENSANCTIONS_API_KEY is missing or empty in .env",
                "credits_consumed": 0,
                "best_hit": None,
                "hits": [],
            }

        if not name or not name.strip():
            return {
                "status": STATUS_OK,
                "tier": TIER_NO_MATCH,
                "reason": "empty_query",
                "message": "Query name is empty",
                "credits_consumed": 0,
                "best_hit": None,
                "hits": [],
            }

        schema = map_schema(search_type)

        # 3. Construct properties payload (lists of strings per FtM specification)
        props: Dict[str, List[str]] = {"name": [name.strip()]}

        birth_val = dob or yob
        if birth_val:
            props["birthDate"] = [str(birth_val).strip()]
        if nationality:
            props["nationality"] = [str(nationality).strip()]
        if country:
            props["country"] = [str(country).strip()]
            props["jurisdiction"] = [str(country).strip()]
        if id_number:
            props["idNumber"] = [str(id_number).strip()]
        if imo:
            props["imoNumber"] = [str(imo).strip()]
        if registration:
            props["registrationNumber"] = [str(registration).strip()]

        for k, v in extra_fields.items():
            if v is not None:
                props[k] = v if isinstance(v, list) else [str(v)]

        query_payload = {
            "queries": {
                "q": {
                    "schema": schema,
                    "properties": props,
                }
            }
        }

        endpoint_url = f"{self.base_url}/match/{self.dataset}"
        headers = {
            "Authorization": f"ApiKey {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "NaughtyOrNot-SanctionChecK/1.0",
        }

        req = urllib.request.Request(
            endpoint_url,
            data=json.dumps(query_payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        http_status = 0
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                http_status = resp.getcode()
                raw_body = resp.read().decode("utf-8")
                data = json.loads(raw_body)

            # Successfully called API: log 1 credit consumed per official docs
            log_usage(
                query=name,
                schema=schema,
                credits_consumed=1,
                http_status=http_status,
            )

            results_raw = (
                data.get("responses", {}).get("q", {}).get("results") or []
            )

            hits = []
            for item in results_raw:
                score = float(item.get("score", 0.0))
                entity_id = item.get("id", "")
                caption = item.get("caption") or (
                    item.get("properties", {}).get("name", [""])[0]
                )
                item_props = item.get("properties") or {}
                datasets = item.get("datasets") or item_props.get("datasets", [])
                topics = item.get("topics") or item_props.get("topics", [])
                url = f"https://www.opensanctions.org/entities/{entity_id}/" if entity_id else ""
                explanation = item.get("features") or item.get("match") or {}

                # Map to project tiers
                if score >= POTENTIAL_MATCH_THRESHOLD:
                    tier = TIER_POTENTIAL_MATCH
                    reason = "score"
                elif score >= POSSIBLE_MATCH_THRESHOLD:
                    tier = TIER_POSSIBLE_MATCH
                    reason = "score"
                elif score >= CANDIDATE_MIN_MATCH:
                    tier = TIER_POSSIBLE_MATCH
                    reason = "score"
                else:
                    tier = TIER_NO_MATCH
                    reason = "low_score"

                hits.append({
                    "name": caption,
                    "score": score,
                    "tier": tier,
                    "reason": reason,
                    "datasets": datasets,
                    "topics": topics,
                    "entity_id": entity_id,
                    "url": url,
                    "explanation": explanation,
                    "schema": item.get("schema", schema),
                    "properties": item_props,
                })

            hits.sort(key=lambda x: x["score"], reverse=True)
            best_hit = hits[0] if hits else None
            top_tier = best_hit["tier"] if best_hit else TIER_NO_MATCH

            return {
                "status": STATUS_OK,
                "tier": top_tier,
                "credits_consumed": 1,
                "http_status": http_status,
                "best_hit": best_hit,
                "hits": hits,
            }

        except urllib.error.HTTPError as e:
            http_status = e.code
            log_usage(
                query=name,
                schema=schema,
                credits_consumed=0,
                http_status=http_status,
            )
            err_body = ""
            try:
                err_body = e.read().decode("utf-8")
            except (OSError, UnicodeDecodeError) as decode_err:
                logger.debug("Failed to decode HTTP error response body: %s", decode_err)

            logger.warning("OpenSanctions HTTP error %s: %s", e.code, err_body)
            return {
                "status": STATUS_ERROR,
                "tier": TIER_NOT_CHECKED,
                "error": f"HTTP {e.code}: {e.reason}",
                "body": err_body,
                "credits_consumed": 0,
                "best_hit": None,
                "hits": [],
            }
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            logger.warning("OpenSanctions unavailable: %s", e)
            return {
                "status": STATUS_UNAVAILABLE,
                "tier": TIER_NOT_CHECKED,
                "error": str(e),
                "credits_consumed": 0,
                "best_hit": None,
                "hits": [],
            }
        except Exception as e:
            logger.error("Unexpected error in OpenSanctions client: %s", e)
            return {
                "status": STATUS_ERROR,
                "tier": TIER_NOT_CHECKED,
                "error": str(e),
                "credits_consumed": 0,
                "best_hit": None,
                "hits": [],
            }
