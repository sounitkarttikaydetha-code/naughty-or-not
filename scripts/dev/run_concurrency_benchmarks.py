"""
Part E2: Concurrency Load Benchmark Script (Zero External Dependencies).
Executes 1, 10, 25, and 50 concurrent screening name checks against the screening engine.
Measures latency (median and 95th percentile), process RSS memory, and CPU utilization.
Reports index sharing mechanisms and records metrics to reviews/concurrency_benchmarks.json.
"""
import concurrent.futures
import ctypes
import json
import math
import os
import statistics
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.screening.tiering import screen_query_all_lists
from modules.watchman.client import WatchmanClient

SAMPLE_QUERIES = [
    ("Vladimir Putin", "Individual"),
    ("Mahan Air", "Airline"),
    ("Sberbank of Russia", "Entity"),
    ("Al-Qaida", "Entity"),
    ("Acme Corp Clean Entity", "Entity"),
    ("Aerocaribbean Airlines", "Airline"),
    ("Kim Jong Un", "Individual"),
    ("Bashar Al-Assad", "Individual"),
    ("Target International Ltd", "Entity"),
    ("Air Koryo", "Airline"),
]


def get_memory_rss_mb() -> float:
    """Return process Working Set Size (RSS) in MB using ctypes on Windows."""
    if sys.platform == "win32":
        try:
            class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
                _fields_ = [
                    ('cb', ctypes.c_uint32),
                    ('PageFaultCount', ctypes.c_uint32),
                    ('PeakWorkingSetSize', ctypes.c_size_t),
                    ('WorkingSetSize', ctypes.c_size_t),
                    ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                    ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                    ('PagefileUsage', ctypes.c_size_t),
                    ('PeakPagefileUsage', ctypes.c_size_t),
                    ('PrivateUsage', ctypes.c_size_t),
                ]
            counters = PROCESS_MEMORY_COUNTERS_EX()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
            fn = getattr(ctypes.windll.kernel32, 'K32GetProcessMemoryInfo', ctypes.windll.psapi.GetProcessMemoryInfo)
            fn.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESS_MEMORY_COUNTERS_EX), ctypes.c_uint32]
            fn.restype = ctypes.c_int
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            if fn(handle, ctypes.byref(counters), counters.cb):
                return round(counters.WorkingSetSize / (1024 * 1024), 1)
        except Exception:
            pass
    return 0.0


def run_single_query(client, query, q_type):
    t0 = time.perf_counter()
    res = screen_query_all_lists(query, client=client, query_type=q_type)
    t1 = time.perf_counter()
    return (t1 - t0) * 1000.0 # ms


def benchmark_concurrency_level(client, level: int, requests_per_level: int = 50):
    mem_before_mb = get_memory_rss_mb()
    queries_to_run = [SAMPLE_QUERIES[i % len(SAMPLE_QUERIES)] for i in range(requests_per_level)]
    latencies = []

    t_wall_start = time.perf_counter()
    t_cpu_start = time.process_time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=level) as executor:
        futures = [executor.submit(run_single_query, client, q, qt) for q, qt in queries_to_run]
        for f in concurrent.futures.as_completed(futures):
            latencies.append(f.result())

    t_wall_end = time.perf_counter()
    t_cpu_end = time.process_time()
    mem_after_mb = get_memory_rss_mb()

    latencies.sort()
    med_latency = statistics.median(latencies)
    p95_idx = int(math.ceil(0.95 * len(latencies))) - 1
    p95_latency = latencies[min(p95_idx, len(latencies) - 1)]

    wall_duration = t_wall_end - t_wall_start
    cpu_duration = t_cpu_end - t_cpu_start
    cpu_utilization_pct = (cpu_duration / max(wall_duration, 0.001)) * 100.0
    qps = len(latencies) / max(wall_duration, 0.001)

    return {
        "concurrency_level": level,
        "total_requests": requests_per_level,
        "elapsed_seconds": round(wall_duration, 3),
        "qps": round(qps, 2),
        "median_latency_ms": round(med_latency, 2),
        "p95_latency_ms": round(p95_latency, 2),
        "min_latency_ms": round(min(latencies), 2),
        "max_latency_ms": round(max(latencies), 2),
        "mem_before_mb": mem_before_mb,
        "mem_after_mb": mem_after_mb,
        "peak_mem_mb": max(mem_before_mb, mem_after_mb),
        "cpu_utilization_pct": round(cpu_utilization_pct, 1),
    }


def main():
    print("======================================================================")
    print("PART E2: CONCURRENCY BENCHMARKS (1, 10, 25, 50 WORKERS)")
    print("======================================================================")
    
    # Warm up client and engine
    client = WatchmanClient(engine="python")
    # Warm up single search
    _ = screen_query_all_lists("Vladimir Putin", client=client, query_type="Individual")

    levels = [1, 10, 25, 50]
    results = {}

    for lvl in levels:
        reqs = 50 if lvl <= 25 else 100
        print(f"Running concurrency level {lvl} ({reqs} requests)...")
        stats = benchmark_concurrency_level(client, lvl, requests_per_level=reqs)
        results[f"concurrency_{lvl}"] = stats
        print(f"  Level {lvl:2d}: Median={stats['median_latency_ms']}ms | P95={stats['p95_latency_ms']}ms | QPS={stats['qps']} | RSS={stats['peak_mem_mb']}MB")

    # Document index sharing mechanism
    report_data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python_version": sys.version,
        "index_sharing_mechanism": (
            "Python Watchman engine singleton (_shared_engine): index is loaded into shared memory "
            "as read-only dictionary data structures. Worker threads execute concurrent rapidfuzz and "
            "metaphone similarity matches without Python-level mutex locks or cross-session serialization."
        ),
        "limits_identified": (
            "GIL (Global Interpreter Lock) in CPython limits CPU scaling to a single core during raw Python execution, "
            "though rapidfuzz C-extensions release GIL during matrix scoring. "
            "For production high-throughput hosting (>100 QPS), multiple Gunicorn/Uvicorn worker processes with shared read-only memory "
            "or pre-forked workers are recommended over pure multithreading."
        ),
        "benchmarks": results,
    }

    out_path = PROJECT_ROOT / "reviews" / "concurrency_benchmarks.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)

    print(f"\nConcurrency benchmarks saved to: {out_path}")
    return report_data


if __name__ == "__main__":
    main()
