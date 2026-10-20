"""Acceptance tests for repository hygiene and secret exclusion (Finding A-05).
Verifies that .gitignore covers databases, screenshots, build outputs,
and that no binary screenshots or db files are tracked in git.
"""

import subprocess
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestRepoHygiene(unittest.TestCase):
    def test_gitignore_covers_critical_patterns(self):
        """.gitignore must cover *.db, reviews/screens/, dist/, build/."""
        gitignore = PROJECT_ROOT / ".gitignore"
        self.assertTrue(gitignore.is_file())
        content = gitignore.read_text(encoding="utf-8")
        patterns = ["*.db", "reviews/screens/", "dist/", "build/"]
        for p in patterns:
            self.assertIn(p, content, f".gitignore must contain {p}")

    def test_no_tracked_screenshots_or_db_files(self):
        """No .png review screenshots or .db SQLite files should be tracked by git."""
        git_exe = r"C:\Program Files\Git\cmd\git.exe"
        cmd = [git_exe, "ls-files", "reviews/screens/*.png", "*.db", "**/*.db"]
        res = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
        tracked = [f for f in res.stdout.splitlines() if f.strip()]
        self.assertEqual(tracked, [], f"Found binary/db files tracked in git: {tracked}")


if __name__ == "__main__":
    unittest.main()
