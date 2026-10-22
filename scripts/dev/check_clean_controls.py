import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.stdout.reconfigure(encoding="utf-8")

from modules.watchman.client import WatchmanClient
from modules.screening.tiering import screen_query_all_lists

client = WatchmanClient(engine="python")

clean_controls = [
    ("Jaipur International Airport Limited", "organisation"),
    ("Adani Airport Holdings Limited", "organisation"),
    ("Air India", "airline"),
    ("IndiGo", "airline"),
    ("InterGlobe Aviation Limited", "airline"),
    ("Tata Steel Limited", "organisation"),
    ("Larsen & Toubro", "organisation"),
    ("SpiceJet", "airline"),
    ("Akasa Air", "airline"),
    ("Bharat Petroleum", "organisation"),
]

print("=" * 80)
print("T8-6A FALSE POSITIVE CONTROL (10 CLEAN CONTROLS)")
print("=" * 80)

total_red = 0
total_orange = 0
total_info = 0

for name, q_type in clean_controls:
    res = screen_query_all_lists(name, client=client, query_type=q_type)
    print(f"\nClean Control: '{name}' ({q_type})")
    for src in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]:
        bh = res[src]["best_hit"]
        red_count = bh.get("red_count", 0)
        orange_count = bh.get("orange_count", 0)
        info_count = bh.get("below_threshold_count", 0)
        
        total_red += red_count
        total_orange += orange_count
        total_info += info_count
        
        tier = bh.get("tier")
        icon = bh.get("tier_icon")
        score = bh.get("score", 0.0)
        reason = bh.get("reason")
        pname = bh.get("primary_name")
        print(f"  [{src}] {icon} {tier} (score={score:.4f}, reason={reason}) | reds={red_count}, oranges={orange_count}, info={info_count} | top='{pname}'")

print("\n" + "=" * 80)
print(f"Total across all 10 clean controls:")
print(f"  RED hits: {total_red} (Target: 0)")
print(f"  ORANGE hits: {total_orange} (Target: <= 3 new)")
print(f"  INFO hits: {total_info}")
print("=" * 80)
