"""
Licensing, Terms of Use & Notices Audit Test Suite (T11 Part K).
Verifies:
- LICENSE.md is proprietary enterprise license
- installer/TERMS_OF_USE.txt exists and is referenced in setup.iss
- installer/setup.iss is rebranded to Clearance Check v1.1.0
- THIRD_PARTY_NOTICES.md contains all mandatory attributions (Moov Watchman, Inter font, OpenSanctions, ReportLab)
- docs/dev/DEVELOPER_TOOLS.md separates dev tools from runtime binary packages
"""

from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestLicensingAndNotices(unittest.TestCase):
    """Test suite ensuring license, terms, and third-party notices integrity."""

    def test_01_license_md_proprietary(self):
        """LICENSE.md must define proprietary enterprise software license."""
        lic_path = PROJECT_ROOT / "LICENSE.md"
        self.assertTrue(lic_path.exists(), "LICENSE.md must exist in project root")
        text = lic_path.read_text(encoding="utf-8")
        self.assertIn("Clearance Check", text)
        self.assertIn("Proprietary Commercial", text)
        self.assertIn("Sounit Karttikay", text)
        self.assertIn("THIRD_PARTY_NOTICES.md", text)

    def test_02_terms_of_use_installer_page(self):
        """installer/TERMS_OF_USE.txt must exist and contain disclaimer."""
        terms_path = PROJECT_ROOT / "installer" / "TERMS_OF_USE.txt"
        self.assertTrue(terms_path.exists(), "installer/TERMS_OF_USE.txt must exist")
        text = terms_path.read_text(encoding="utf-8")
        self.assertIn("CLEARANCE CHECK", text)
        self.assertIn("NOT LEGAL ADVICE", text)
        self.assertIn("ZERO DATA TRANSMISSION", text)

    def test_03_inno_setup_branding_and_license_binding(self):
        """setup.iss must use TERMS_OF_USE.txt and be branded Clearance Check v1.1.0."""
        iss_path = PROJECT_ROOT / "installer" / "setup.iss"
        self.assertTrue(iss_path.exists(), "installer/setup.iss must exist")
        text = iss_path.read_text(encoding="utf-8")
        self.assertIn('#define MyAppName "Clearance Check"', text)
        self.assertTrue(any(f'#define MyAppVersion "{v}"' in text for v in ["1.1.3", "1.1.2", "1.1.1", "1.1.0"]))
        self.assertIn("LicenseFile=TERMS_OF_USE.txt", text)
        self.assertIn("Programs\\ClearanceCheck", text)

    def test_04_third_party_notices_complete(self):
        """THIRD_PARTY_NOTICES.md must attribute all required upstream components."""
        notices_path = PROJECT_ROOT / "THIRD_PARTY_NOTICES.md"
        self.assertTrue(notices_path.exists(), "THIRD_PARTY_NOTICES.md must exist")
        text = notices_path.read_text(encoding="utf-8")
        self.assertIn("Moov Watchman", text)
        self.assertIn("Inter Typeface", text)
        self.assertIn("OpenSanctions Crawlers", text)
        self.assertIn("ReportLab", text)
        self.assertIn("DarkGarden", text)
        self.assertIn("Streamlit", text)
        self.assertIn("OpenPyXL", text)

    def test_05_developer_tools_documentation(self):
        """docs/dev/DEVELOPER_TOOLS.md must document developer-only utilities."""
        dev_tools_path = PROJECT_ROOT / "docs" / "dev" / "DEVELOPER_TOOLS.md"
        self.assertTrue(dev_tools_path.exists(), "docs/dev/DEVELOPER_TOOLS.md must exist")
        text = dev_tools_path.read_text(encoding="utf-8")
        self.assertIn("pytest", text)
        self.assertIn("Playwright", text)
        self.assertIn("Inno Setup", text)
        self.assertIn("None of the developer tools", text)


if __name__ == "__main__":
    unittest.main()
