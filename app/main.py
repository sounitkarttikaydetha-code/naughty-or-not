"""Entrypoint delegating to app.py."""
import os
import runpy
import sys
from pathlib import Path

# Ensure project root is at index 0 of sys.path and is current working directory
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(str(ROOT))

app_path = ROOT / "app.py"
runpy.run_path(str(app_path), run_name="__main__")
