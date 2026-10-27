import time
import statistics
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.watchman.client import WatchmanClient
from modules.screening.tiering import screen_query_all_lists
from modules.screening.country import CountryEngine
from modules.ownership.engine import UBOEngine
from modules.ownership.models import Counterparty, Holding

def run_benchmarks():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 70)
    print("CLEARANCE CHECK v1.1.2 5-RUN BENCHMARK (NAME, COUNTRY, UBO)")
    print("=" * 70)

    # Warm up client and engines
    client = WatchmanClient(engine="python")
    country_engine = CountryEngine()
    ubo_engine = UBOEngine()

    # Setup sample UBO structure: 4 tiers, 5 entities
    target = Counterparty(name="Target Industrial Corp")
    holdings = [
        Holding(shareholder_name="Intermediate Holding Ltd", entity_name="Target Industrial Corp", share_pct=60.0),
        Holding(shareholder_name="Global Parent SA", entity_name="Intermediate Holding Ltd", share_pct=100.0),
        Holding(shareholder_name="Blocked Oligarch LLC", entity_name="Global Parent SA", share_pct=55.0, is_blocked=True, blocked_source="us_ofac"),
    ]

    # 1. Name Screening (Warm query)
    name_times = []
    for _ in range(5):
        t0 = time.perf_counter()
        _ = screen_query_all_lists("Gazprom Neft PJSC", client=client, query_type="organisation")
        name_times.append(time.perf_counter() - t0)

    # 2. Country Screening (Multi-regime comprehensive check)
    country_times = []
    for _ in range(5):
        t0 = time.perf_counter()
        _ = country_engine.screen_country("Syria")
        _ = country_engine.screen_country("Crimea")
        _ = country_engine.screen_country("Iran")
        _ = country_engine.screen_country("Russia")
        country_times.append(time.perf_counter() - t0)

    # 3. UBO Screening (Multi-tier tree evaluation)
    ubo_times = []
    for _ in range(5):
        t0 = time.perf_counter()
        _ = ubo_engine.evaluate_structure(
            counterparty=target,
            holdings=holdings,
            auto_screen=False,
        )
        ubo_times.append(time.perf_counter() - t0)

    print("\n1. Name Screening (Gazprom Neft PJSC across 15 sources):")
    print(f"   Min:    {min(name_times)*1000:.2f} ms")
    print(f"   Median: {statistics.median(name_times)*1000:.2f} ms")
    print(f"   Max:    {max(name_times)*1000:.2f} ms")

    print("\n2. Country Screening (4 comprehensive checks: Syria, Crimea, Iran, Russia):")
    print(f"   Min:    {min(country_times)*1000:.2f} ms")
    print(f"   Median: {statistics.median(country_times)*1000:.2f} ms")
    print(f"   Max:    {max(country_times)*1000:.2f} ms")

    print("\n3. UBO Screening (4-tier ownership cascade & blocked evaluation):")
    print(f"   Min:    {min(ubo_times)*1000:.2f} ms")
    print(f"   Median: {statistics.median(ubo_times)*1000:.2f} ms")
    print(f"   Max:    {max(ubo_times)*1000:.2f} ms")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    run_benchmarks()
