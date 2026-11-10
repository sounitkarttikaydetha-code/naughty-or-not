"""
Index Provider Port (Abstract Interface).
Defines contracts for searching local offline index across all 5 mandatory lists
(us_ofac, us_csl, uk_csl, eu_csl, un_csl) plus aviation and domestic lists.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class IndexProviderPort(ABC):
    """Port for candidate retrieval from in-memory or database inverted index."""

    @abstractmethod
    def screen_all_lists(
        self,
        query: str,
        query_type: Optional[str] = None,
        identifier_type: Optional[str] = None,
        identifier_val: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Screen query across all 5 mandatory lists and return raw hit dictionaries."""
        pass

    @abstractmethod
    def search_candidates(
        self,
        query: str,
        query_type: Optional[str] = None,
        min_match: float = 0.60,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Search across sources and return raw candidate dictionaries per source."""
        pass

    @abstractmethod
    def get_source_publication_dates(self) -> Dict[str, str]:
        """Return published dates of cached sanction lists."""
        pass

    @abstractmethod
    def get_source_record_counts(self) -> Dict[str, int]:
        """Return total record counts indexed per source."""
        pass

    @abstractmethod
    def get_raw_record(self, source_id: str, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve raw entity record by source and ID."""
        pass
