"""
Moov Watchman Python Client
Client for querying the locally-running Moov Watchman sanctions search engine.
"""

import json
import logging
import os
import urllib.parse
import urllib.request
import urllib.error
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class WatchmanClient:
    """Client for interacting with the local Moov Watchman HTTP API."""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 10.0):
        """
        Initialize the Watchman client.

        :param base_url: URL where Watchman is hosted. Defaults to WATCHMAN_URL env var or http://localhost:8084.
        :param timeout: Request timeout in seconds.
        """
        self.base_url = (base_url or os.getenv("WATCHMAN_URL", "http://localhost:8084")).rstrip("/")
        self.timeout = float(timeout)

    def _make_request(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Helper to make HTTP GET requests and return parsed JSON or unavailable status.
        Never crashes when Watchman is unavailable or times out.
        """
        url = f"{self.base_url}{path}"
        if params:
            clean_params = {k: v for k, v in params.items() if v is not None}
            if clean_params:
                url = f"{url}?{urllib.parse.urlencode(clean_params)}"

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "NaughtyOrNot-WatchmanClient/1.0", "Accept": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                status_code = resp.getcode()
                raw_body = resp.read().decode("utf-8")
                if raw_body.strip():
                    try:
                        data = json.loads(raw_body)
                        return {
                            "status": "ok",
                            "status_code": status_code,
                            "data": data
                        }
                    except json.JSONDecodeError:
                        return {
                            "status": "ok",
                            "status_code": status_code,
                            "data": raw_body
                        }
                return {
                    "status": "ok",
                    "status_code": status_code,
                    "data": {}
                }
        except urllib.error.HTTPError as e:
            logger.warning("Watchman HTTP error on %s: %s", url, e)
            body = ""
            try:
                body = e.read().decode("utf-8")
            except (OSError, UnicodeDecodeError) as decode_err:
                logger.debug("Failed to decode Watchman error body: %s", decode_err)

            return {
                "status": "error",
                "status_code": e.code,
                "error": f"HTTP {e.code}: {e.reason}",
                "body": body
            }
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            logger.warning("Watchman unavailable at %s: %s", url, e)
            return {
                "status": "unavailable",
                "status_code": None,
                "error": str(e),
                "url": url
            }
        except Exception as e:
            logger.error("Unexpected error querying Watchman at %s: %s", url, e)
            return {
                "status": "unavailable",
                "status_code": None,
                "error": f"Unexpected error: {e}",
                "url": url
            }

    def health(self) -> Dict[str, Any]:
        """
        Check health of Watchman service.
        Moov Watchman responds to /ping with 'PONG' and /v2/data/refresh with status.
        Returns clean dict with status and healthy boolean.
        """
        res = self._make_request("/ping")
        if res.get("status") == "ok":
            return {
                "status": "ok",
                "healthy": True,
                "status_code": res.get("status_code"),
                "details": res.get("data")
            }
        elif res.get("status") == "unavailable":
            return {
                "status": "unavailable",
                "healthy": False,
                "error": res.get("error")
            }
        else:
            return {
                "status": res.get("status", "error"),
                "healthy": False,
                "error": res.get("error", "Unknown health check failure"),
                "status_code": res.get("status_code")
            }


    def list_info(self) -> Dict[str, Any]:
        """
        Retrieve loaded lists, record counts, hashes and timestamps from /v2/listinfo.
        """
        res = self._make_request("/v2/listinfo")
        if res.get("status") == "ok":
            return {
                "status": "ok",
                "lists": res.get("data", {})
            }
        return {
            "status": "unavailable" if res.get("status") == "unavailable" else "error",
            "lists": {},
            "error": res.get("error")
        }

    def search(
        self,
        name: str,
        type: Optional[str] = None,
        min_match: float = 0.80,
        **fields: Any
    ) -> Dict[str, Any]:
        """
        Screen a name against Watchman via /v2/search.

        :param name: Entity name to screen
        :param type: Entity type (person, entity, etc.)
        :param min_match: Match threshold between 0.0 and 1.0 (default 0.80)
        :param fields: Additional search filters/parameters
        :return: Clean dict with search results or unavailable error
        """
        params = {
            "name": name,
            "minMatch": min_match,
            **fields
        }
        if type:
            params["type"] = type

        res = self._make_request("/v2/search", params=params)
        if res.get("status") == "ok":
            return {
                "status": "ok",
                "query": {
                    "name": name,
                    "type": type,
                    "minMatch": min_match
                },
                "results": res.get("data", {})
            }
        return {
            "status": "unavailable" if res.get("status") == "unavailable" else "error",
            "query": {
                "name": name,
                "type": type,
                "minMatch": min_match
            },
            "results": {},
            "error": res.get("error")
        }
