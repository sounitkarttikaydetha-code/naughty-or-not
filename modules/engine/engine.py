"""
Local Python Screening Engine
Drop-in replacement for Moov Watchman (v1.2.2).
Complies with Watchman's HTTP API response format and scoring semantics.
"""

from collections import defaultdict
import hashlib
import logging
from pathlib import Path
import pickle
import re
import time
from typing import Any, Dict, List, Optional, Set, Tuple

import metaphone
from modules.screening.config import PHONETIC_ENABLED
from modules.engine.loader import (
    EntityRecord,
    load_ofac_sdn,
    load_us_csl,
    load_uk_csl,
    load_eu_csl,
    load_un_csl,
)
from modules.engine.name_prep import (
    canonicalize_legal_forms,
    normalize_text,
    prepare_name,
    remove_stopwords,
)
from modules.engine.scoring import score_query_against_entity_names, SOUNDEX_MAP_LOWER

logger = logging.getLogger(__name__)

LIST_SOURCES = ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]


def select_candidates_for_query(
    tokens: List[str],
    token_index: Dict[str, List[int]],
    partition_size: int,
) -> List[int]:
    """
    Port of Watchman internal/index/corpus.go nameCandidateIndices and distinctiveQueryTokens.
    Selects candidates by intersecting distinctive query tokens (DF <= 0.20),
    dropping overly frequent tokens (DF >= 2x next), and falling back to union or full partition.
    """
    if not tokens or partition_size == 0:
        return list(range(partition_size))

    # Find hitting postings
    hitting: List[List[int]] = []
    for tok in tokens:
        hits = token_index.get(tok)
        if hits:
            hitting.append(hits)

    if not hitting:
        # Runaway-token guard: no real entity token exceeds ~36 chars.
        # If every query token is >50 chars and none hit the index, skip the
        # full partition scan -- it would be O(N) Jaro-Winkler for no benefit.
        if all(len(tok) > 50 for tok in tokens):
            return []
        # Pure typo / unknown tokens: scan partition to preserve fuzzy recall
        return list(range(partition_size))

    # Sort hitting lists by ascending frequency (rarest first)
    hitting.sort(key=len)

    # If >= 2 tokens, drop the most frequent if it's >= 2x more frequent than next
    if len(hitting) >= 2:
        most_len = len(hitting[-1])
        next_len = len(hitting[-2])
        if most_len >= 2 * next_len:
            hitting = hitting[:-1]

    # Keep tokens where DF <= 0.20
    distinctive = [h for h in hitting if (len(h) / partition_size) <= 0.20]
    if not distinctive:
        distinctive = hitting

    distinctive.sort(key=len)

    # Intersect from rarest
    cands = set(distinctive[0])
    for h in distinctive[1:]:
        cands &= set(h)
        if not cands:
            break

    # If intersection is empty, fallback to union
    if not cands:
        for h in distinctive:
            cands |= set(h)

    # If candidates cover > 50% of partition, scan full partition
    if len(cands) > (0.5 * partition_size):
        return list(range(partition_size))

    return list(cands)


class PythonEngine:
    """
    In-memory Python Screening Engine with inverted token candidate selection.
    Exposes the same interface as WatchmanClient (search, listinfo, health).
    """

    @staticmethod
    def _resolve_default_data_dir() -> Path:
        try:
            from modules.common.paths import get_lists_dir, get_seed_data_dir
            active_raw = get_lists_dir() / "raw"
            if active_raw.is_dir() and any(active_raw.iterdir()):
                return active_raw
            seed_raw = get_seed_data_dir() / "raw"
            if seed_raw.is_dir():
                return seed_raw
        except Exception:
            pass
        return Path("data/raw")

    def __init__(self, data_dir: Optional[Path] = None):
        self.data_dir = data_dir or self._resolve_default_data_dir()
        self.records_by_source: Dict[str, List[EntityRecord]] = {s: [] for s in LIST_SOURCES}
        self.token_index_by_source: Dict[str, Dict[str, List[int]]] = {s: defaultdict(list) for s in LIST_SOURCES}
        self.prefix_index_by_source: Dict[str, Dict[str, List[int]]] = {s: defaultdict(list) for s in LIST_SOURCES}
        self.phonetic_index_by_source: Dict[str, Dict[str, List[int]]] = {s: defaultdict(list) for s in LIST_SOURCES}
        self.phonetic_enabled: bool = PHONETIC_ENABLED
        self.id_index_by_source: Dict[str, Dict[str, List[int]]] = {s: defaultdict(list) for s in LIST_SOURCES}
        self.hashes_by_source: Dict[str, str] = {s: "" for s in LIST_SOURCES}
        self.source_errors: Dict[str, str] = {}
        self.loaded_at: Optional[str] = None
        self._load_all_sources()

    def _build_indexes_for_source(self, src: str) -> None:
        """Build token, prefix, and identifier inverted indices for fast candidate retrieval."""
        t_idx = defaultdict(list)
        p_idx = defaultdict(list)
        ph_idx = defaultdict(list)
        id_idx = defaultdict(list)
        records = self.records_by_source.get(src, [])
        for idx, rec in enumerate(records):
            tokens: Set[str] = set(rec.primary_tokens)
            for alt_tokens in rec.alt_tokens_list:
                tokens.update(alt_tokens)
            for h_tokens in rec.historical_tokens_list:
                tokens.update(h_tokens)

            for t in tokens:
                t_idx[t].append(idx)
                if len(t) >= 3:
                    p_idx[t[:3]].append(idx)
                if len(t) >= 4:
                    p_code, s_code = metaphone.doublemetaphone(t)
                    if p_code:
                        ph_idx[p_code].append(idx)
                    if s_code and s_code != p_code:
                        ph_idx[s_code].append(idx)

            for ident in rec.identifiers:
                id_idx[ident].append(idx)

        self.token_index_by_source[src] = dict(t_idx)
        self.prefix_index_by_source[src] = dict(p_idx)
        self.phonetic_index_by_source[src] = dict(ph_idx)
        self.id_index_by_source[src] = dict(id_idx)

    def _load_all_sources(self) -> None:
        """Load all 5 official sanctions lists with disk caching keyed by file signatures."""
        loaders = [
            ("us_ofac", self.data_dir / "us_ofac_sdn.csv", load_ofac_sdn),
            ("us_csl", self.data_dir / "us_csl.csv", load_us_csl),
            ("uk_csl", self.data_dir / "uk_csl.csv", load_uk_csl),
            ("eu_csl", self.data_dir / "eu_csl.xml", load_eu_csl),
            ("un_csl", self.data_dir / "un_csl.xml", load_un_csl),
        ]

        # 1. Compute composite cache key from source file signatures (name, size, mtime)
        file_signatures = []
        for src, path, _ in loaders:
            if path.is_file():
                st = path.stat()
                file_signatures.append(f"{src}:{path.name}:{st.st_size}:{st.st_mtime_ns}")
            else:
                file_signatures.append(f"{src}:missing")

        cache_key = hashlib.sha256((";".join(file_signatures) + ":ph_v1").encode()).hexdigest()[:24]

        cache_dir = None
        try:
            from modules.common.paths import get_cache_dir
            cache_dir = get_cache_dir()
        except Exception:
            cache_dir = self.data_dir.parent / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file = cache_dir / f"engine_index_{cache_key}.pkl"

        # 2. Try loading pre-built index from disk cache with SHA-256 integrity check
        hash_file = cache_dir / f"engine_index_{cache_key}.sha256"
        if cache_file.is_file() and hash_file.is_file():
            try:
                t0 = time.perf_counter()
                expected_sha = hash_file.read_text(encoding="utf-8").strip()
                with open(cache_file, "rb") as f:
                    data = f.read()
                computed_sha = hashlib.sha256(data).hexdigest()
                if computed_sha != expected_sha:
                    raise ValueError(f"Cache integrity check failed: expected {expected_sha[:12]}, got {computed_sha[:12]}")
                cached = pickle.loads(data)
                self.records_by_source = cached["records_by_source"]
                self.token_index_by_source = cached["token_index_by_source"]
                self.prefix_index_by_source = cached["prefix_index_by_source"]
                self.phonetic_index_by_source = cached.get("phonetic_index_by_source", {})
                self.id_index_by_source = cached["id_index_by_source"]
                self.hashes_by_source = cached["hashes_by_source"]
                self.source_errors = cached.get("source_errors", {})
                self.loaded_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                logger.info(f"Loaded screening index from cache in {time.perf_counter() - t0:.3f} s")
                return
            except Exception as ce:
                logger.warning(f"Could not load engine cache {cache_file}: {ce}; falling back to raw build")

        # 3. Fallback: Parse raw files and build indices
        for src, path, loader_fn in loaders:
            try:
                if not path.is_file():
                    self.source_errors[src] = f"File missing: {path}"
                    self.records_by_source[src] = []
                    self.hashes_by_source[src] = ""
                    continue
                recs, file_hash = loader_fn(path)
                self.records_by_source[src] = recs
                self.hashes_by_source[src] = file_hash
                self._build_indexes_for_source(src)
            except Exception as e:
                logger.error(f"Error loading {src} from {path}: {e}")
                self.source_errors[src] = str(e)
                self.records_by_source[src] = []
                self.hashes_by_source[src] = ""

        self.loaded_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        # 4. Save built index to disk cache atomically
        if any(self.records_by_source.values()):
            try:
                tmp_cache = cache_dir / f"engine_index_{cache_key}.tmp"
                cache_payload = {
                    "records_by_source": self.records_by_source,
                    "token_index_by_source": self.token_index_by_source,
                    "prefix_index_by_source": self.prefix_index_by_source,
                    "phonetic_index_by_source": self.phonetic_index_by_source,
                    "id_index_by_source": self.id_index_by_source,
                    "hashes_by_source": self.hashes_by_source,
                    "source_errors": self.source_errors,
                }
                cache_bytes = pickle.dumps(cache_payload, protocol=pickle.HIGHEST_PROTOCOL)
                cache_sha = hashlib.sha256(cache_bytes).hexdigest()
                with open(tmp_cache, "wb") as f:
                    f.write(cache_bytes)
                tmp_cache.replace(cache_file)
                hash_file = cache_dir / f"engine_index_{cache_key}.sha256"
                hash_file.write_text(cache_sha, encoding="utf-8")
                # Clean up older caches
                for old_c in cache_dir.glob("engine_index_*.*"):
                    if old_c != cache_file and old_c != hash_file:
                        try:
                            old_c.unlink()
                        except Exception:
                            pass
            except Exception as pe:
                logger.warning(f"Failed to save engine disk cache: {pe}")

    def health(self) -> Dict[str, Any]:
        """Health check matching Watchman's /health endpoint."""
        total_records = sum(len(recs) for recs in self.records_by_source.values())
        healthy = total_records > 0 and len(self.source_errors) == 0
        return {
            "healthy": healthy,
            "engine": "python",
            "status": "ok" if healthy else "incomplete",
            "total_records": total_records,
            "errors": self.source_errors,
        }

    def listinfo(self) -> Dict[str, Any]:
        """List metadata matching Watchman's /v2/listinfo endpoint."""
        counts = {s: len(self.records_by_source[s]) for s in LIST_SOURCES}
        return {
            "lists": counts,
            "listHashes": self.hashes_by_source,
            "version": "python-v1.0.0",
            "startedAt": self.loaded_at,
            "endedAt": self.loaded_at,
        }

    def search(
        self,
        name: str,
        type: Optional[str] = None,
        min_match: float = 0.50,
        source: Optional[str] = None,
        limit: int = 50,
    ) -> Dict[str, Any]:
        """
        Search entities matching Watchman's /v2/search endpoint.
        Returns a dictionary with identical schema to WatchmanClient.search.
        """
        if not name or not name.strip():
            return {
                "status": "ok",
                "query": {"name": name, "minMatch": min_match, "limit": limit},
                "results": {"query": name, "entities": []},
            }

        q_norm, _ = prepare_name(name, type or "")
        q_tokens = remove_stopwords(q_norm)
        if not q_tokens:
            return {
                "status": "ok",
                "query": {"name": name, "minMatch": min_match, "limit": limit},
                "results": {"query": name, "entities": []},
            }

        if source and (source in self.source_errors or not self.records_by_source.get(source)):
            err = self.source_errors.get(source, f"Source {source} not loaded or empty")
            return {
                "status": "unavailable",
                "error": err,
                "query": {"name": name, "type": type, "source": source, "minMatch": min_match, "limit": limit},
                "results": {"query": name, "entities": []},
            }

        if not any(self.records_by_source.values()):
            return {
                "status": "unavailable",
                "error": "All search lists failed to load",
                "query": {"name": name, "type": type, "minMatch": min_match, "limit": limit},
                "results": {"query": name, "entities": []},
            }

        target_sources = [source] if (source and source in self.records_by_source) else LIST_SOURCES
        candidates: List[Tuple[float, EntityRecord]] = []
        target_type = type.lower() if type else None
        seen_cand_ids = set()

        # Check direct identifier match across target sources (Record ID, IMO, Tail, MSN)
        q_raw_clean = name.strip().lower()
        q_raw_alnum = re.sub(r"[^\w]", "", q_raw_clean)

        for src in target_sources:
            id_map = self.id_index_by_source.get(src, {})
            matching_indices = set(id_map.get(q_raw_clean, [])) | set(id_map.get(q_raw_alnum, []))
            for idx in matching_indices:
                rec = self.records_by_source[src][idx]
                if target_type and rec.entity_type != target_type:
                    continue
                candidates.append((1.0, rec))
                seen_cand_ids.add((rec.source, rec.source_id))

        for src in target_sources:
            records = self.records_by_source.get(src, [])
            if not records:
                continue

            # Candidate selection: port of Watchman internal/index/corpus.go
            cand_indices = select_candidates_for_query(
                tokens=q_tokens,
                token_index=self.token_index_by_source[src],
                partition_size=len(records),
            )

            q_soundex = {SOUNDEX_MAP_LOWER.get(t[0], t[0]) for t in q_tokens if t}

            for rec_idx in cand_indices:
                rec = records[rec_idx]
                if (rec.source, rec.source_id) in seen_cand_ids:
                    continue
                if target_type and rec.entity_type != target_type:
                    continue
                if q_soundex and getattr(rec, "soundex_classes", None) and q_soundex.isdisjoint(rec.soundex_classes):
                    continue

                score = score_query_against_entity_names(
                    query_tokens=q_tokens,
                    primary_tokens=rec.primary_tokens,
                    alt_names_tokens=rec.alt_tokens_list,
                    historical_tokens=rec.historical_tokens_list,
                    query_name=q_norm,
                    primary_name=rec.prepared_name,
                )
                if score >= min_match:
                    candidates.append((score, rec))
                    seen_cand_ids.add((rec.source, rec.source_id))

            # 2. Phonetic retrieval pass: extra candidates unioned (T8-6A)
            if getattr(self, "phonetic_enabled", True):
                extra_phonetic: Set[int] = set()
                cand_set = set(cand_indices)
                part_size = len(records)
                for t in q_tokens:
                    if len(t) >= 4:
                        p_code, s_code = metaphone.doublemetaphone(t)
                        for code in {p_code, s_code} - {"", None}:
                            ph_hits = self.phonetic_index_by_source.get(src, {}).get(code, [])
                            if ph_hits and (len(ph_hits) / part_size) <= 0.20:
                                for h_idx in ph_hits:
                                    if h_idx not in cand_set and h_idx not in extra_phonetic:
                                        extra_phonetic.add(h_idx)
                                        if len(extra_phonetic) >= 50:
                                            break
                            if len(extra_phonetic) >= 50:
                                break

                for h_idx in extra_phonetic:
                    rec = records[h_idx]
                    if (rec.source, rec.source_id) in seen_cand_ids:
                        continue
                    if target_type and rec.entity_type != target_type:
                        continue
                    score = score_query_against_entity_names(
                        query_tokens=q_tokens,
                        primary_tokens=rec.primary_tokens,
                        alt_names_tokens=rec.alt_tokens_list,
                        historical_tokens=rec.historical_tokens_list,
                        query_name=q_norm,
                        primary_name=rec.prepared_name,
                    )
                    if score >= min_match:
                        candidates.append((score, rec))
                        seen_cand_ids.add((rec.source, rec.source_id))

        # Sort descending by score across all sources
        candidates.sort(key=lambda x: x[0], reverse=True)
        top_hits = candidates[:limit]

        entities_out = []
        for score, rec in top_hits:
            ent = dict(rec.raw_entity)
            ent["match"] = score
            entities_out.append(ent)

        return {
            "status": "ok",
            "query": {
                "name": name,
                "type": type,
                "source": source,
                "minMatch": min_match,
                "limit": limit,
            },
            "results": {
                "query": name,
                "entities": entities_out,
            },
        }
