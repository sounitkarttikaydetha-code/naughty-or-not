"""
Unit tests for OpenSanctions client and credit guard.
"""

from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from modules.opensanctions.client import (
    OpenSanctionsClient,
    STATUS_DISABLED,
    STATUS_NOT_RUN,
    TIER_NOT_CHECKED,
    credits_used,
    map_schema,
)


class TestOpenSanctionsClient(unittest.TestCase):
    """Test suite for OpenSanctions client credit guard and contract."""

    def test_without_key_returns_disabled_and_no_network_call(self):
        """When API key is missing, return DISABLED and make no network call."""
        client = OpenSanctionsClient(api_key="")
        self.assertFalse(client.is_configured())

        with patch("urllib.request.urlopen") as mock_urlopen:
            res = client.match("Aeroflot", search_type="airline", use_opensanctions=True)
            self.assertEqual(res["status"], STATUS_DISABLED)
            self.assertEqual(res["tier"], TIER_NOT_CHECKED)
            self.assertIn("missing", res["message"].lower())
            mock_urlopen.assert_not_called()

    def test_use_opensanctions_false_makes_no_call_and_no_log(self):
        """When use_opensanctions=False, no call is made and nothing is logged."""
        client = OpenSanctionsClient(api_key="mock-key-123")
        initial_usage = credits_used()

        with patch("urllib.request.urlopen") as mock_urlopen:
            res = client.match("Aeroflot", search_type="airline", use_opensanctions=False)
            self.assertEqual(res["status"], STATUS_NOT_RUN)
            self.assertEqual(res["tier"], TIER_NOT_CHECKED)
            self.assertIn("not requested", res["message"].lower())
            mock_urlopen.assert_not_called()

        after_usage = credits_used()
        self.assertEqual(after_usage["total_calls"], initial_usage["total_calls"])
        self.assertEqual(after_usage["total_credits"], initial_usage["total_credits"])

    def test_schema_mapping(self):
        """Verify internal search types map to proper FollowTheMoney schemas."""
        self.assertEqual(map_schema("person"), "Person")
        self.assertEqual(map_schema("organisation"), "Company")
        self.assertEqual(map_schema("company"), "Company")
        self.assertEqual(map_schema("airline"), "Company")
        self.assertEqual(map_schema("aircraft"), "Airplane")
        self.assertEqual(map_schema("vessel"), "Vessel")


if __name__ == "__main__":
    unittest.main()
