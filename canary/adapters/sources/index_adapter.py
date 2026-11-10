"""
Index Provider Adapter for Clearance Check Canary.
Wraps the high-performance inverted token & phonetic index, returning structured candidates.
"""
from typing import Any, Dict, List, Optional
from pathlib import Path

from canary.application.ports.index_provider import IndexProviderPort


class PythonIndexAdapter(IndexProviderPort):
    def __init__(self, data_dir: Optional[Path] = None):
        from modules.watchman.client import WatchmanClient, get_python_engine
        self.client = WatchmanClient(engine="python")
        self.engine = get_python_engine()

    def screen_all_lists(
        self,
        query: str,
        query_type: Optional[str] = None,
        identifier_type: Optional[str] = None,
        identifier_val: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Screen query across all 5 mandatory lists and return raw hit dictionaries."""
        from modules.screening.tiering import screen_query_all_lists
        identifiers = [identifier_val] if identifier_val else None
        return screen_query_all_lists(
            query=query,
            client=self.client,
            query_type=query_type,
            identifiers=identifiers,
        )

    def search_candidates(
        self,
        query: str,
        query_type: Optional[str] = None,
        min_match: float = 0.60,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Search across sources and return raw candidate dictionaries per source."""
        candidates: Dict[str, List[Dict[str, Any]]] = {}
        for src in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]:
            raw_res = self.engine.search(name=query, min_match=min_match, source=src)
            c_list = []
            if raw_res and isinstance(raw_res.get("results"), dict):
                c_list = raw_res["results"].get("entities", [])
            elif raw_res and src in raw_res:
                c_list = raw_res[src]
            candidates[src] = c_list
        return candidates

    def get_source_publication_dates(self) -> Dict[str, str]:
        """Return publication dates."""
        try:
            from modules.common.source_manager import SourceManager
            mgr = SourceManager()
            return mgr.get_source_dates()
        except Exception:
            return {
                "us_ofac": "2026-10-24",
                "us_csl": "2026-10-24",
                "uk_csl": "2026-10-24",
                "eu_csl": "2026-10-24",
                "un_csl": "2026-10-24",
            }

    def get_source_record_counts(self) -> Dict[str, int]:
        """Return record count per source."""
        counts = {}
        for src, recs in self.engine.records_by_source.items():
            counts[src] = len(recs)
        return counts

    def get_raw_record(self, source_id: str, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve raw entity by ID."""
        records = self.engine.records_by_source.get(source_id, [])
        for rec in records:
            if str(rec.record_id) == str(record_id):
                return {
                    "source_id": source_id,
                    "record_id": rec.record_id,
                    "primary_name": rec.primary_name,
                    "entity_type": rec.entity_type,
                    "aliases": rec.alt_names,
                    "addresses": rec.addresses,
                    "identification_numbers": rec.identifications,
                    "programmes": rec.programmes,
                    "remarks": rec.remarks,
                }
        return None
