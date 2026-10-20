"""Client for screening against Indian Ministry of Home Affairs (MHA) UAPA lists:
- First Schedule: Terrorist Organisations
- Fourth Schedule: Terrorist Individuals
- Unlawful Associations: Section 3 UAPA

Provides screening functions with exact token and core-name matching,
returning 🔴 POTENTIAL_MATCH, ✅ NO_MATCH, or ⚪ NOT_CHECKED.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from modules.india.parser import (
    parse_first_schedule,
    parse_fourth_schedule,
    parse_unlawful_associations,
    SOURCES,
)

logger = logging.getLogger(__name__)

PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)

GENERIC_WORDS = {
    "organization", "organisations", "organisation", "front", "party",
    "group", "association", "committee", "force", "army", "network",
    "limited", "ltd", "pvt", "private", "corp", "inc", "international",
    "services", "airport", "india", "indian", "national",
}


def normalize_text(text: Optional[str]) -> str:
    """Normalize text for screening: lowercase, strip punctuation, squash spaces."""
    if not text:
        return ""
    clean = PUNCT_RE.sub(" ", text.lower())
    return " ".join(clean.split())


def get_tokens(text: str) -> List[str]:
    """Get non-empty normalized tokens."""
    return [t for t in normalize_text(text).split() if t]


def score_match(query: str, target: str) -> Tuple[bool, float]:
    """Score matching between query and target.
    Returns:
      (matched: bool, score: float)
    """
    q_norm = normalize_text(query)
    t_norm = normalize_text(target)

    if not q_norm or not t_norm:
        return False, 0.0

    # 1. Exact normalized equality
    if q_norm == t_norm:
        return True, 1.0

    q_tokens = get_tokens(query)
    t_tokens = get_tokens(target)

    if not q_tokens or not t_tokens:
        return False, 0.0

    q_set = set(q_tokens)
    t_set = set(t_tokens)

    # Distinctive (non-generic) tokens
    q_distinctive = [t for t in q_tokens if t not in GENERIC_WORDS and len(t) > 2]
    t_distinctive = [t for t in t_tokens if t not in GENERIC_WORDS and len(t) > 2]

    # If all tokens are generic, require exact token match
    if not q_distinctive or not t_distinctive:
        if q_tokens == t_tokens:
            return True, 1.0
        return False, 0.0

    # 2. Token subset matches
    if q_set.issubset(t_set) and any(t in t_distinctive for t in q_tokens):
        # Ratio of query length to target length
        ratio = len(q_tokens) / len(t_tokens)
        return True, 0.80 + 0.15 * ratio

    if t_set.issubset(q_set) and any(t in q_distinctive for t in t_tokens):
        ratio = len(t_tokens) / len(q_tokens)
        return True, 0.75 + 0.15 * ratio

    # 3. Core distinctive phrase match
    if len(q_distinctive) >= 2:
        q_phrase = " ".join(q_distinctive)
        t_phrase = " ".join(t_distinctive)
        if q_phrase in t_norm or t_phrase in q_norm:
            return True, 0.70

    return False, 0.0


class IndiaClient:
    """Client for screening entities against Indian MHA UAPA designations."""

    def __init__(
        self,
        first_schedule_path: Optional[Path] = None,
        fourth_schedule_path: Optional[Path] = None,
        unlawful_assoc_path: Optional[Path] = None,
    ):
        self.fs_path = first_schedule_path
        self.ind_path = fourth_schedule_path
        self.unl_path = unlawful_assoc_path
        self._load_data()

    def _load_data(self) -> None:
        """Load and cache all lists."""
        self.first_schedule = parse_first_schedule(self.fs_path)
        self.fourth_schedule = parse_fourth_schedule(self.ind_path)
        self.unlawful_associations = parse_unlawful_associations(self.unl_path)

    def screen(self, query: str, search_type: str = "ALL") -> Dict[str, Any]:
        """Screen query against MHA UAPA lists.
        search_type can be 'ALL', 'INDIVIDUAL', or 'ORGANIZATION'.
        Returns:
          {
            "tier": "POTENTIAL_MATCH" | "NO_MATCH" | "NOT_CHECKED",
            "tier_icon": "🔴" | "✅" | "⚪",
            "source": "India (MHA / UAPA)",
            "matches": [ ... ],
            "top_match": { ... } or None,
            "error": Optional[str],
            "last_good_date": str
          }
        """
        failed_sources = []
        last_date = "2026-10-01"
        for src in [self.first_schedule, self.fourth_schedule, self.unlawful_associations]:
            if src.get("status") == "FAILED":
                failed_sources.append(src.get("error"))
                last_date = src.get("last_good_date", last_date)

        if failed_sources:
            return {
                "tier": "NOT_CHECKED",
                "tier_icon": "⚪",
                "source": "India (MHA / UAPA)",
                "finding": "SOURCE_UNAVAILABLE",
                "error": "; ".join(filter(None, failed_sources)),
                "last_good_date": last_date,
                "matches": [],
                "top_match": None,
            }

        clean_query = query.strip()
        if not clean_query:
            return {
                "tier": "NO_MATCH",
                "tier_icon": "✅",
                "source": "India (MHA / UAPA)",
                "matches": [],
                "top_match": None,
            }

        candidate_lists = []
        st = search_type.upper()
        if st in ["ALL", "ORGANIZATION", "COMPANY", "ENTITY"]:
            candidate_lists.extend(self.first_schedule.get("entities", []))
            candidate_lists.extend(self.unlawful_associations.get("entities", []))
        if st in ["ALL", "INDIVIDUAL", "PERSON"]:
            candidate_lists.extend(self.fourth_schedule.get("entities", []))

        matches = []
        for ent in candidate_lists:
            best_score = 0.0
            best_matched_name = None
            best_matched_field = None

            # Test primary name
            prim_match, prim_score = score_match(clean_query, ent.get("name", ""))
            if prim_match and prim_score > best_score:
                best_score = prim_score
                best_matched_name = ent.get("name")
                best_matched_field = "primary_name"

            # Test aliases
            for alias in ent.get("aliases", []):
                al_match, al_score = score_match(clean_query, alias)
                # Give slight edge to exact alias match if primary was only partial
                if al_match and (al_score > best_score or (al_score == 1.0 and best_score < 1.0)):
                    best_score = al_score
                    best_matched_name = alias
                    best_matched_field = "alias"

            if best_matched_name and best_score >= 0.70:
                match_rec = {
                    "id": ent.get("id"),
                    "schema": ent.get("schema"),
                    "authority_id": ent.get("authority_id"),
                    "listed_name": ent.get("name"),
                    "matched_name": best_matched_name,
                    "matched_field": best_matched_field,
                    "score": round(best_score, 4),
                    "parent_organization": ent.get("parent_organization"),
                    "schedule": ent.get("schedule"),
                    "source_url": ent.get("source_url"),
                }
                matches.append(match_rec)

        if matches:
            # Sort by score descending, then prefer entity with parent_organization or shorter name
            matches.sort(
                key=lambda m: (
                    m["score"],
                    1 if m.get("parent_organization") else 0,
                    -len(m.get("listed_name", "")),
                ),
                reverse=True,
            )
            top = matches[0]
            return {
                "tier": "POTENTIAL_MATCH",
                "tier_icon": "🔴",
                "source": "India (MHA / UAPA)",
                "matches": matches,
                "top_match": top,
                "parent_organization": top.get("parent_organization"),
                "schedule": top.get("schedule"),
            }

        return {
            "tier": "NO_MATCH",
            "tier_icon": "✅",
            "source": "India (MHA / UAPA)",
            "matches": [],
            "top_match": None,
        }
