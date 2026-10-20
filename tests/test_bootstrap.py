"""Acceptance test for clean-room reproducibility bootstrap (Finding A-04).
Verifies that scripts/init_data.py exists and is documented in README.md.
"""

import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestCleanRoomBootstrap(unittest.TestCase):
    def test_init_data_script_exists(self):
        """scripts/init_data.py must exist to bootstrap clean clones."""
        script_path = PROJECT_ROOT / "scripts" / "init_data.py"
        self.assertTrue(script_path.is_file(), "scripts/init_data.py must exist")

    def test_readme_documents_init_data(self):
        """README.md must document running scripts/init_data.py."""
        readme = PROJECT_ROOT / "README.md"
        self.assertTrue(readme.is_file())
        content = readme.read_text(encoding="utf-8")
        self.assertIn("scripts/init_data.py", content, "README.md must reference scripts/init_data.py")


if __name__ == "__main__":
    unittest.main()
