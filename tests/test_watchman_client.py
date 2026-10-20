"""
Unit and acceptance tests for Watchman client.
"""

import unittest
from modules.watchman.client import WatchmanClient


class TestWatchmanClientUnavailable(unittest.TestCase):
    """Test that client gracefully handles unavailable Watchman service without crashing."""

    def test_client_handles_service_down_gracefully(self):
        # Point to an unreachable local port where Watchman is guaranteed not to run
        unreachable_port = 59999
        client = WatchmanClient(base_url=f"http://127.0.0.1:{unreachable_port}", timeout=1.0)

        # 1. Health check should not crash and should return status='unavailable'
        health = client.health()
        self.assertIsInstance(health, dict)
        self.assertEqual(health.get("status"), "unavailable")
        self.assertFalse(health.get("healthy"))
        self.assertIn("error", health)

        # 2. list_info check should not crash and should return status='unavailable'
        info = client.list_info()
        self.assertIsInstance(info, dict)
        self.assertEqual(info.get("status"), "unavailable")
        self.assertEqual(info.get("lists"), {})
        self.assertIn("error", info)

        # 3. search should not crash and should return status='unavailable'
        search_res = client.search(name="Sberbank", min_match=0.80)
        self.assertIsInstance(search_res, dict)
        self.assertEqual(search_res.get("status"), "unavailable")
        self.assertEqual(search_res.get("results"), {})
        self.assertIn("error", search_res)

    def test_live_watchman_when_running(self):
        """If local Watchman is running, verify health, list_info, and search."""
        client = WatchmanClient()
        health = client.health()
        if not health.get("healthy"):
            self.skipTest("Local Watchman instance is not running on localhost:8084")

        # 1. Test health
        self.assertEqual(health.get("status"), "ok")

        # 2. Test list info
        info = client.list_info()
        self.assertEqual(info.get("status"), "ok")
        lists = info.get("lists", {})
        self.assertIn("us_ofac", lists.get("lists", {}))
        self.assertGreater(lists.get("lists", {}).get("us_ofac", 0), 0)

        # 3. Test search
        res = client.search(name="VTB Bank", min_match=0.80)
        self.assertEqual(res.get("status"), "ok")
        entities = res.get("results", {}).get("entities", [])
        self.assertGreaterEqual(len(entities), 1)



if __name__ == "__main__":
    unittest.main()
