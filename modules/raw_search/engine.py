"""Raw search execution engine.
Performs plain text search across full records with no scoring, no tiers,
and provides highlighted snippets and official verification links.
"""

from datetime import datetime, timezone
import html
import logging
from pathlib import Path
import re
import sqlite3
import unicodedata
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

logger = logging.getLogger(__name__)

INDEX_DB_PATH = Path("data/raw_index.db")
SOURCES_YAML_PATH = Path("config/sources.yaml")


def load_sources_config() -> Dict[str, Dict[str, Any]]:
    """Load sources metadata from config/sources.yaml."""
    if not SOURCES_YAML_PATH.is_file():
        return {}
    with open(SOURCES_YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    res = {}
    for s in data.get("sources", []):
        sid = s.get("id")
        if sid:
            res[sid] = s
    return res


def strip_accents(text: str) -> str:
    """Strip accents and diacritics."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )


def extract_highlighted_snippet(
    text: str, query: str, window: int = 50, fold_accents: bool = True, case_sensitive: bool = False
) -> str:
    """
    Find match in text and return snippet with <b>...</b> highlighting.
    """
    if not text or not query:
        return ""

    haystack = text
    needle = query
    if fold_accents:
        haystack_norm = strip_accents(text)
        needle_norm = strip_accents(query)
    else:
        haystack_norm = text
        needle_norm = query

    if not case_sensitive:
        haystack_norm = haystack_norm.lower()
        needle_norm = needle_norm.lower()

    idx = haystack_norm.find(needle_norm)
    if idx == -1:
        # Try word-by-word
        words = needle_norm.split()
        for w in words:
            idx = haystack_norm.find(w)
            if idx != -1:
                needle_norm = w
                break

    if idx == -1:
        # Return prefix of text
        snippet = text[: window * 2].strip()
        return html.escape(snippet) + ("..." if len(text) > len(snippet) else "")

    start = max(0, idx - window)
    end = min(len(text), idx + len(query) + window)

    before = html.escape(text[start:idx])
    matched = html.escape(text[idx : idx + len(query)])
    after = html.escape(text[idx + len(query) : end])

    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""

    return f"{prefix}{before}<b>{matched}</b>{after}{suffix}"


def determine_matched_field(
    row: sqlite3.Row, query: str, fold_accents: bool = True, case_sensitive: bool = False
) -> str:
    """Identify which field triggered the match."""
    q = strip_accents(query) if fold_accents else query
    if not case_sensitive:
        q = q.lower()

    def check(val: Optional[str]) -> bool:
        if not val:
            return False
        v = strip_accents(val) if fold_accents else val
        if not case_sensitive:
            v = v.lower()
        return q in v

    if check(row["record_id"]):
        return "Record ID"
    if check(row["primary_name"]):
        return "Primary Name"
    if check(row["all_names"]):
        return "Aliases / Names"
    return "All Text / Remarks"


class RawSearchEngine:
    """Engine executing raw text queries against the local FTS5 database."""

    def __init__(self, db_path: Path = INDEX_DB_PATH):
        self.db_path = db_path
        self.sources_cfg = load_sources_config()

    def get_source_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Return index status for every source."""
        statuses = {}
        # Default all known sources
        for sid, scfg in self.sources_cfg.items():
            statuses[sid] = {
                "source": sid,
                "authority": scfg.get("authority", sid),
                "status": "⚪",
                "count": 0,
                "list_date": scfg.get("publication_date", ""),
            }

        if not self.db_path.is_file():
            return statuses

        try:
            con = sqlite3.connect(str(self.db_path))
            cur = con.cursor()
            rows = cur.execute("SELECT source, status, record_count, list_date FROM source_meta;").fetchall()
            for src, st, cnt, dt in rows:
                statuses[src] = {
                    "source": src,
                    "authority": self.sources_cfg.get(src, {}).get("authority", src),
                    "status": "OK" if st == "OK" else "⚪",
                    "count": cnt,
                    "list_date": dt or self.sources_cfg.get(src, {}).get("publication_date", ""),
                }
            con.close()
        except Exception as e:
            logger.warning(f"Error reading source_meta: {e}")
        return statuses

    def search(
        self,
        query: str,
        match_option: str = "Contains",
        fold_accents_and_case: bool = True,
        search_field: str = "All fields",
        selected_sources: Optional[List[str]] = None,
        limit: int = 200,
    ) -> Dict[str, Any]:
        """
        Execute raw text search.
        
        Parameters:
          query: search term
          match_option: 'Contains' | 'Whole word' | 'Exact phrase' | 'Starts with'
          fold_accents_and_case: bool (default True)
          search_field: 'All fields' | 'Names only' | 'IDs and numbers only'
          selected_sources: list of source IDs to filter (default: all)
          limit: maximum number of records to return (default: 200)

        Returns:
          {
            "status": "OK" | "INVALID_QUERY" | "NO_RESULTS" | "DB_UNAVAILABLE",
            "message": Optional[str],
            "query": str,
            "total_matches": int,
            "limit_reached": bool,
            "results": [ ... ],
            "source_statuses": { ... },
            "execution_time_ms": float
          }
        """
        import time
        start_time = time.time()

        clean_q = query.strip() if query else ""

        # Validation Rule: Minimum length: 3 characters, except in "IDs and numbers only".
        if search_field != "IDs and numbers only" and len(clean_q) < 3:
            return {
                "status": "INVALID_QUERY",
                "message": "Query must be at least 3 characters long (except in 'IDs and numbers only').",
                "query": query,
                "total_matches": 0,
                "limit_reached": False,
                "results": [],
                "source_statuses": self.get_source_statuses(),
                "execution_time_ms": 0.0,
            }

        if not clean_q:
            return {
                "status": "INVALID_QUERY",
                "message": "Query cannot be empty.",
                "query": query,
                "total_matches": 0,
                "limit_reached": False,
                "results": [],
                "source_statuses": self.get_source_statuses(),
                "execution_time_ms": 0.0,
            }

        if not self.db_path.is_file():
            return {
                "status": "DB_UNAVAILABLE",
                "message": "Raw index database is not built. Rebuild raw index first.",
                "query": query,
                "total_matches": 0,
                "limit_reached": False,
                "results": [],
                "source_statuses": self.get_source_statuses(),
                "execution_time_ms": 0.0,
            }

        con = sqlite3.connect(str(self.db_path))
        con.row_factory = sqlite3.Row
        cur = con.cursor()

        # Build SQL condition
        # Target columns based on search_field
        if search_field == "Names only":
            target_cols = ["primary_name", "all_names"]
        elif search_field == "IDs and numbers only":
            target_cols = ["record_id"]
        else:
            target_cols = ["record_id", "primary_name", "all_names", "all_text"]

        params: List[Any] = []
        where_clauses: List[str] = []

        # Source filter
        if selected_sources:
            placeholders = ",".join(["?"] * len(selected_sources))
            where_clauses.append(f"source IN ({placeholders})")
            params.extend(selected_sources)

        # Match strategy
        # For standard text queries, LIKE or FTS5 MATCH
        # Using LIKE allows exact 'Contains' across substrings and hyphens without tokenizer quirks
        like_pattern = ""
        if match_option == "Exact phrase":
            # Exact phrase inside field
            col_clauses = [f"{col} LIKE ?" for col in target_cols]
            where_clauses.append(f"({' OR '.join(col_clauses)})")
            params.extend([f"%{clean_q}%"] * len(target_cols))
        elif match_option == "Starts with":
            col_clauses = [f"{col} LIKE ?" for col in target_cols]
            where_clauses.append(f"({' OR '.join(col_clauses)})")
            params.extend([f"{clean_q}%"] * len(target_cols))
        elif match_option == "Whole word":
            # Word boundary regex or space-padded LIKE
            col_clauses = [
                f"({col} LIKE ? OR {col} LIKE ? OR {col} LIKE ? OR {col} = ?)"
                for col in target_cols
            ]
            where_clauses.append(f"({' OR '.join(col_clauses)})")
            for _ in target_cols:
                params.extend([f"{clean_q} %", f"% {clean_q} %", f"% {clean_q}", clean_q])
        else:
            # Contains (default)
            col_clauses = [f"{col} LIKE ?" for col in target_cols]
            where_clauses.append(f"({' OR '.join(col_clauses)})")
            params.extend([f"%{clean_q}%"] * len(target_cols))

        sql = f"SELECT source, record_id, primary_name, all_names, all_text, source_url, list_date FROM raw_index"
        if where_clauses:
            sql += " WHERE " + " AND ".join(where_clauses)
        sql += f" LIMIT {limit + 1};"

        try:
            rows = cur.execute(sql, params).fetchall()
        except Exception as e:
            logger.error(f"Error executing raw search: {e}")
            con.close()
            return {
                "status": "ERROR",
                "message": f"Query execution error: {e}",
                "query": query,
                "total_matches": 0,
                "limit_reached": False,
                "results": [],
                "source_statuses": self.get_source_statuses(),
                "execution_time_ms": (time.time() - start_time) * 1000,
            }

        con.close()

        limit_reached = len(rows) > limit
        result_rows = rows[:limit]

        formatted_results = []
        for r in result_rows:
            matched_field = determine_matched_field(
                r, clean_q, fold_accents=fold_accents_and_case, case_sensitive=not fold_accents_and_case
            )
            # Text extract
            extract_src = r["all_text"] if matched_field == "All Text / Remarks" else (r["all_names"] or r["primary_name"])
            snippet = extract_highlighted_snippet(
                extract_src, clean_q, fold_accents=fold_accents_and_case, case_sensitive=not fold_accents_and_case
            )

            # Build official verify URL
            source_id = r["source"]
            cfg = self.sources_cfg.get(source_id, {})
            verify_url = cfg.get("verify_url") or r["source_url"] or ""
            rec_template = cfg.get("record_url_template", "")
            rec_id = r["record_id"]
            if rec_template and rec_id:
                direct_url = rec_template.replace("{id}", str(rec_id))
            else:
                direct_url = verify_url

            formatted_results.append({
                "source": source_id,
                "authority": cfg.get("authority", source_id),
                "record_id": rec_id,
                "primary_name": r["primary_name"],
                "matched_field": matched_field,
                "text_extract": snippet,
                "list_date": r["list_date"] or cfg.get("publication_date", ""),
                "verify_url": direct_url,
                "search_page_url": verify_url,
                "has_record_link": bool(rec_template),
            })

        elapsed_ms = (time.time() - start_time) * 1000

        return {
            "status": "OK" if formatted_results else "NO_RESULTS",
            "message": "Showing top 200 — more may exist; refine the search" if limit_reached else None,
            "query": query,
            "total_matches": len(formatted_results),
            "limit_reached": limit_reached,
            "results": formatted_results,
            "source_statuses": self.get_source_statuses(),
            "execution_time_ms": elapsed_ms,
        }
