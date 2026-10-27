"""
30-Minute Endurance Soak Test for Item A5.
Runs 360 searches at a 5-second cadence (~30 minutes),
recording start and end memory (RSS, Peak) and handle counts.
Outputs results to reviews/soak_30min_results.json.
"""

import ctypes
from ctypes import wintypes
import gc
import json
import os
from pathlib import Path
import sys
import time
from typing import Dict, Any, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.screening.tiering import screen_query_all_lists
from modules.watchman.client import get_python_engine


class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


def get_process_memory_mb() -> Tuple[float, float]:
    if sys.platform != "win32":
        return 0.0, 0.0
    try:
        psapi = ctypes.windll.psapi
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS_EX), wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        h_process = kernel32.GetCurrentProcess()
        pmc = PROCESS_MEMORY_COUNTERS_EX()
        pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
        if psapi.GetProcessMemoryInfo(h_process, ctypes.byref(pmc), pmc.cb):
            return round(pmc.WorkingSetSize / (1024 * 1024), 2), round(pmc.PeakWorkingSetSize / (1024 * 1024), 2)
    except Exception:
        pass
    return 0.0, 0.0


def get_process_handle_count() -> int:
    if sys.platform != "win32":
        return 0
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.GetProcessHandleCount.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        kernel32.GetProcessHandleCount.restype = wintypes.BOOL
        h_process = kernel32.GetCurrentProcess()
        handle_count = wintypes.DWORD()
        if kernel32.GetProcessHandleCount(h_process, ctypes.byref(handle_count)):
            return int(handle_count.value)
    except Exception:
        pass
    return 0


def main():
    print("=" * 60)
    print("STARTING 30-MINUTE SOAK TEST (360 iterations, 5s cadence)")
    print("=" * 60)

    # Warm up engine
    get_python_engine()
    gc.collect()

    start_rss, start_peak = get_process_memory_mb()
    start_handles = get_process_handle_count()
    start_time = time.time()

    print(f"Start Working Set: {start_rss} MB (Peak: {start_peak} MB)")
    print(f"Start Handle Count: {start_handles}")
    print(f"Start Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}")

    soak_queries = [
        ("Aeroflot Russian Airlines", "Airline"),
        ("Tata Steel Limited", "Organisation"),
        ("Vladimir Putin", "Person"),
        ("RA-73093", "Aircraft"),
        ("SIBERIA", "Vessel"),
        ("Sberbank", "Organisation"),
        ("S7 Airlines", "Airline"),
        ("Air India", "Organisation"),
    ]

    iterations = 360
    errors = []
    latencies = []

    for i in range(iterations):
        t0 = time.perf_counter()
        q_name, q_type = soak_queries[i % len(soak_queries)]
        try:
            res = screen_query_all_lists(query=q_name, query_type=q_type)
            dt_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(dt_ms)
        except Exception as e:
            errors.append(f"Iteration {i+1} failed: {e}")

        elapsed_iter = time.perf_counter() - t0
        if i < iterations - 1 and elapsed_iter < 5.0:
            time.sleep(5.0 - elapsed_iter)

        if (i + 1) % 30 == 0:
            cur_rss, _ = get_process_memory_mb()
            cur_handles = get_process_handle_count()
            print(f"[{i+1:03d}/{iterations}] Iteration {i+1} complete. Memory: {cur_rss} MB, Handles: {cur_handles}")

    gc.collect()
    end_time = time.time()
    end_rss, end_peak = get_process_memory_mb()
    end_handles = get_process_handle_count()
    total_duration_s = round(end_time - start_time, 2)

    results = {
        "status": "PASSED" if len(errors) == 0 and abs(end_handles - start_handles) <= 5 else "FAILED",
        "iterations": iterations,
        "total_duration_seconds": total_duration_s,
        "start_memory_mb": start_rss,
        "end_memory_mb": end_rss,
        "memory_growth_mb": round(end_rss - start_rss, 2),
        "peak_memory_mb": end_peak,
        "start_handles": start_handles,
        "end_handles": end_handles,
        "handle_difference": end_handles - start_handles,
        "error_count": len(errors),
        "errors": errors,
        "latency_stats_ms": {
            "min": round(min(latencies), 2) if latencies else 0,
            "median": round(sorted(latencies)[len(latencies) // 2], 2) if latencies else 0,
            "max": round(max(latencies), 2) if latencies else 0,
        },
    }

    out_file = PROJECT_ROOT / "reviews" / "soak_30min_results.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("\n" + "=" * 60)
    print(f"SOAK TEST COMPLETED in {total_duration_s}s ({results['status']})")
    print(f"Memory: {start_rss} MB -> {end_rss} MB (diff: {results['memory_growth_mb']} MB)")
    print(f"Handles: {start_handles} -> {end_handles} (diff: {results['handle_difference']})")
    print(f"Results written to: {out_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()
