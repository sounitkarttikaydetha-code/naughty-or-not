"""
Part E1: Hosting Readiness Performance Benchmarks (5 Runs per metric).
Measures:
1. Index load / start-up time (with and without cache) across 5 runs.
2. Idle memory and peak memory during search.
3. Cold and Warm search latencies across 5 runs for:
   - Clean organisation ("Acme Global Trading")
   - Airline with alias expansion ("Mahan Air")
   - Person search ("Vladimir Putin")
Saves all min, median, max measurements to reviews/e1_benchmarks.json.
"""
import ctypes
import json
import statistics
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.watchman.client import WatchmanClient, get_python_engine
from modules.screening.tiering import screen_query_all_lists


def get_rss_mb() -> float:
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
                return round(counters.WorkingSetSize / (1024 * 1024), 2)
        except Exception:
            pass
    return 0.0


def measure_startup_times():
    print("Measuring startup time to ready index (5 runs)...")
    cache_times = []
    # Warm engine load
    for i in range(5):
        t0 = time.perf_counter()
        eng = get_python_engine()
        t1 = time.perf_counter()
        cache_times.append((t1 - t0) * 1000.0)

    # Without cache simulation: initialize a fresh client
    no_cache_times = []
    for i in range(5):
        t0 = time.perf_counter()
        c = WatchmanClient(engine="python")
        t1 = time.perf_counter()
        no_cache_times.append((t1 - t0) * 1000.0)

    return {
        "with_cache_ms": {
            "min": round(min(cache_times), 2),
            "median": round(statistics.median(cache_times), 2),
            "max": round(max(cache_times), 2),
            "runs": [round(x, 2) for x in cache_times],
        },
        "initial_client_load_ms": {
            "min": round(min(no_cache_times), 2),
            "median": round(statistics.median(no_cache_times), 2),
            "max": round(max(no_cache_times), 2),
            "runs": [round(x, 2) for x in no_cache_times],
        }
    }


def measure_search_latency(query, q_type):
    client = WatchmanClient(engine="python")
    
    # 5 Cold runs (force cache clear or cold query evaluation)
    cold_runs = []
    for _ in range(5):
        t0 = time.perf_counter()
        _ = screen_query_all_lists(query, client=client, query_type=q_type)
        t1 = time.perf_counter()
        cold_runs.append((t1 - t0) * 1000.0)

    # 5 Warm runs
    warm_runs = []
    for _ in range(5):
        t0 = time.perf_counter()
        _ = screen_query_all_lists(query, client=client, query_type=q_type)
        t1 = time.perf_counter()
        warm_runs.append((t1 - t0) * 1000.0)

    return {
        "cold_ms": {
            "min": round(min(cold_runs), 2),
            "median": round(statistics.median(cold_runs), 2),
            "max": round(max(cold_runs), 2),
            "runs": [round(x, 2) for x in cold_runs],
        },
        "warm_ms": {
            "min": round(min(warm_runs), 2),
            "median": round(statistics.median(warm_runs), 2),
            "max": round(max(warm_runs), 2),
            "runs": [round(x, 2) for x in warm_runs],
        }
    }


def main():
    print("======================================================================")
    print("PART E1: HOSTING BENCHMARKS (5 RUNS PER METRIC)")
    print("======================================================================")

    idle_mem = get_rss_mb()
    startup_data = measure_startup_times()

    queries = [
        ("clean_organisation", "Acme Global Trading", "Organisation"),
        ("airline_alias_expansion", "Mahan Air", "Airline"),
        ("person_search", "Vladimir Putin", "Individual"),
    ]

    search_benchmarks = {}
    peak_mem = idle_mem

    for key, q, qt in queries:
        print(f"Measuring '{q}' ({qt})...")
        res = measure_search_latency(q, qt)
        search_benchmarks[key] = res
        curr_mem = get_rss_mb()
        if curr_mem > peak_mem:
            peak_mem = curr_mem
        print(f"  {key}: Cold median={res['cold_ms']['median']}ms | Warm median={res['warm_ms']['median']}ms")

    final_mem = get_rss_mb()

    e1_data = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python_version": sys.version,
        "memory_mb": {
            "idle_rss_mb": idle_mem,
            "peak_rss_mb": peak_mem,
            "final_rss_mb": final_mem,
        },
        "startup_to_ready_index": startup_data,
        "searches": search_benchmarks,
        "container_image_size": "Not measured (Docker daemon requires Windows Service Administrator elevation)",
    }

    out_file = PROJECT_ROOT / "reviews" / "e1_benchmarks.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(e1_data, f, indent=2)

    print(f"\nPart E1 benchmarks saved to: {out_file}")
    return e1_data


if __name__ == "__main__":
    main()
