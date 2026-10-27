"""
Guard test for Rule 9: Author's Signature & Easter Egg Integrity.
Fails if the exact signature line is missing or altered in any required location:
(a) README.md (bottom of file)
(b) app/about.py (comment block at end)
(c) EASTER_EGG.txt (root and distribution)
(d) app.py (About box, behind the small '…' link)
(e) deploy README (or deploy/README.md)
Compares by exact text and SHA-256 stored in tests/fixtures/signature.txt.
"""

import hashlib
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "signature.txt"


def get_canonical_signature() -> str:
    assert FIXTURE_PATH.is_file(), f"Signature fixture not found at {FIXTURE_PATH}"
    return FIXTURE_PATH.read_text(encoding="utf-8").strip()


def compute_sig_hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


class TestSignatureGuard(unittest.TestCase):
    def setUp(self):
        self.expected_signature = get_canonical_signature()
        self.expected_hash = compute_sig_hash(self.expected_signature)

    def test_01_fixture_hash(self):
        """Verify fixture is non-empty and contains author's exact signature."""
        self.assertIn("Naughty or not, a brainchild of Sounit Karttikay", self.expected_signature)
        self.assertIn("no AIs were sanctioned in the making of this tool", self.expected_signature)

    def test_02_readme_location(self):
        """(a) Bottom of README.md."""
        readme = PROJECT_ROOT / "README.md"
        self.assertTrue(readme.is_file())
        content = readme.read_text(encoding="utf-8")
        last_line = [l.strip() for l in content.splitlines() if l.strip()][-1]
        if last_line.startswith(">"):
            last_line = last_line.lstrip(">").strip()
        self.assertEqual(compute_sig_hash(last_line), self.expected_hash, "README.md signature hash mismatch")

    def test_03_about_py_location(self):
        """(b) Comment block at end of app/about.py."""
        about_py = PROJECT_ROOT / "app" / "about.py"
        self.assertTrue(about_py.is_file())
        content = about_py.read_text(encoding="utf-8")
        last_line = [l.strip() for l in content.splitlines() if l.strip()][-1]
        if last_line.startswith("#"):
            last_line = last_line.lstrip("#").strip()
        self.assertEqual(compute_sig_hash(last_line), self.expected_hash, "app/about.py signature hash mismatch")

    def test_04_easter_egg_txt_location(self):
        """(c) EASTER_EGG.txt."""
        egg_txt = PROJECT_ROOT / "EASTER_EGG.txt"
        self.assertTrue(egg_txt.is_file())
        content = egg_txt.read_text(encoding="utf-8").strip()
        self.assertEqual(compute_sig_hash(content), self.expected_hash, "EASTER_EGG.txt signature hash mismatch")

    def test_05_about_box_link_location(self):
        """(d) About box in app.py behind small '…' link."""
        app_py = PROJECT_ROOT / "app.py"
        self.assertTrue(app_py.is_file())
        content = app_py.read_text(encoding="utf-8")
        self.assertIn(self.expected_signature, content, "app.py About box must contain exact signature")

    def test_06_deploy_readme_location(self):
        """(e) deploy README."""
        deploy_readme = PROJECT_ROOT / "deploy" / "README.md"
        alt_deploy = Path("D:/naughty-or-not-deploy/README.md")
        target = deploy_readme if deploy_readme.is_file() else (alt_deploy if alt_deploy.is_file() else None)
        if target:
            content = target.read_text(encoding="utf-8")
            last_line = [l.strip() for l in content.splitlines() if l.strip()][-1]
            if last_line.startswith(">"):
                last_line = last_line.lstrip(">").strip()
            self.assertEqual(compute_sig_hash(last_line), self.expected_hash, "deploy README.md signature mismatch")


if __name__ == "__main__":
    unittest.main()
