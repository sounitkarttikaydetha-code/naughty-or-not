import time
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.engine import PythonEngine

t0 = time.perf_counter()
engine = PythonEngine()
print(f"Engine initialized in {time.perf_counter() - t0:.2f}s")
print("Health:", engine.health())
print("Listinfo counts:", engine.listinfo()["lists"])

t1 = time.perf_counter()
res = engine.search("Sberbank", min_match=0.70, limit=5)
search_time = time.perf_counter() - t1
print(f"Search completed in {search_time * 1000:.2f}ms")
for e in res["results"]["entities"]:
    print(f"{e['match']:.4f} | {e['sourceList']} | {e['sourceID']} | {e['name']}")
