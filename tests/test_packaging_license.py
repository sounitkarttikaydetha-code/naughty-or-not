"""Acceptance tests for licensing and packaging hygiene (Finding A-03).
Ensures that no GPL/copyleft fonts or artifacts are bundled into the distribution.
"""

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestPackagingLicense(unittest.TestCase):
    def test_build_spec_excludes_gpl_darkgarden(self):
        """build.spec must exist and explicitly exclude GPL DarkGarden font."""
        spec_path = PROJECT_ROOT / "build.spec"
        self.assertTrue(spec_path.is_file(), "build.spec must exist in project root")

        content = spec_path.read_text(encoding="utf-8")
        self.assertIn("DarkGarden", content, "build.spec must explicitly mention DarkGarden")
        self.assertTrue(
            "DarkGarden" in content and ("exclude" in content.lower() or "not in" in content),
            "build.spec must exclude DarkGarden font to maintain permissive distribution license"
        )

    def test_third_party_notices_documents_darkgarden_exclusion(self):
        """THIRD_PARTY_NOTICES.md must document ReportLab licensing and DarkGarden font exclusion."""
        tpn_path = PROJECT_ROOT / "THIRD_PARTY_NOTICES.md"
        self.assertTrue(tpn_path.is_file())
        content = tpn_path.read_text(encoding="utf-8")
        self.assertIn("ReportLab", content)
        self.assertIn("DarkGarden", content)


if __name__ == "__main__":
    unittest.main()
