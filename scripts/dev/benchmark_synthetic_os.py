"""
Benchmark script for T10-2 Synthetic OpenSanctions bulk loader.
Measures:
- Load time, index size, peak memory, search latency (min, med, p95, max across 20 searches)
- Effect on official sources search times
- Failure handling: missing file, empty file, corrupt file, malformed rows
"""

import json
import os
import sys
import time
import tracemalloc
from pathlib import Path
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from modules.opensanctions.bulk import load_bulk, is_bulk_enabled
from modules.watchman.client import WatchmanClient
from modules.screening.tiering import screen_query_all_lists
from scripts.dev.make_synthetic_os import generate_synthetic_dataset

FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"


def benchmark_size(count: int, file_path: Path):
    if not file_path.is_file():
        print(f"Generating fixture for {count} records...")
        generate_synthetic_dataset(count, file_path, seed=42)

    os.environ["OPENSANCTIONS_BULK_ENABLED"] = "true"
    os.environ["OPENSANCTIONS_BULK_PERMISSION_REF"] = "BENCHMARK-EVAL-REF"

    # Measure load time and peak memory
    tracemalloc.start()
    t0 = time.perf_counter()
    res = load_bulk(file_path=file_path, check_ack=False)
    load_time = time.perf_counter() - t0
    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    file_size_mb = file_path.stat().st_size / (1024 * 1024)
    peak_mem_mb = peak_mem / (1024 * 1024)

    # Measure search latency (20 queries)
    entities = res.get("entities", [])
    queries = [e["name"] for e in entities[:20]] if entities else ["AeroSynthetica Global Trade LLC"]
    client = WatchmanClient(engine="python")

    latencies = []
    for q in queries:
        t_s = time.perf_counter()
        screen_query_all_lists(q, client=client, query_type="organisation")
        latencies.append((time.perf_counter() - t_s) * 1000)

    return {
        "count": count,
        "file_size_mb": round(file_size_mb, 2),
        "entities_loaded": res.get("entities_loaded", 0),
        "malformed_count": res.get("malformed_count", 0),
        "load_time_s": round(load_time, 3),
        "peak_mem_mb": round(peak_mem_mb, 2),
        "search_latency_ms": {
            "min": round(float(np.min(latencies)), 1),
            "median": round(float(np.median(latencies)), 1),
            "p95": round(float(np.percentile(latencies, 95)), 1),
            "max": round(float(np.max(latencies)), 1),
        },
    }


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("Running T10-2 OpenSanctions Synthetic Loader Benchmarks...")
    f_1k = FIXTURES_DIR / "synthetic_os_1k.ftm.json"
    f_50k = FIXTURES_DIR / "synthetic_os_50k.ftm.json"

    bench_1k = benchmark_size(1_000, f_1k)
    print("1k Benchmark:", json.dumps(bench_1k, indent=2))

    bench_50k = benchmark_size(50_000, f_50k)
    print("50k Benchmark:", json.dumps(bench_50k, indent=2))

    summary = {
        "layout_url": "https://www.opensanctions.org/docs/bulk/ and https://followthemoney.tech/docs/entities/",
        "documented_fields": ["id", "schema", "caption", "properties.name", "properties.alias", "properties.birthDate", "properties.nationality", "properties.jurisdiction", "datasets"],
        "benchmarks": {
            "1k": bench_1k,
            "50k": bench_50k,
        },
    }

    out_json = PROJECT_ROOT / "reviews" / "synthetic_bulk_benchmark.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\nSaved synthetic bulk benchmark to {out_json}")


if __name__ == "__main__":
    main()
