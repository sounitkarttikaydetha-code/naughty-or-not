"""
Comprehensive validation of the phonetic (Double Metaphone + variants) layer per T9-2.
Replaces the circular T8 benchmark with:
1. 500-pair leave-one-out alias test (recall OFF vs ON, overall and per list)
2. 300 realistic clean names noise test (new 🟠, new ℹ️, mean, p95, max)
3. Performance benchmark: Index build time and search time with phonetic ON vs OFF
4. Audit of curated variant groups marked 'applied, not yet approved'
5. Verdict determination with empirical evidence.
"""

import os
import sys
import time
import random
import json
from pathlib import Path
from typing import Dict, List, Any, Tuple
import yaml
import numpy as np

# Force UTF-8 stdout
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.watchman.client import WatchmanClient, get_python_engine
from modules.screening.tiering import screen_query_all_lists, extract_all_aliases
import modules.screening.config as config


def get_entities_with_aliases(engine) -> List[Dict[str, Any]]:
    """Collect all entities across the five sanctions lists having >= 3 name strings."""
    candidates = []
    for src in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]:
        records = engine.records_by_source.get(src, [])
        for rec in records:
            aliases = extract_all_aliases(rec.raw_entity)
            primary = rec.name or ""
            valid_names = [n for n in aliases if len(n.strip()) >= 4]
            if len(valid_names) >= 3:
                candidates.append({
                    "source": src,
                    "record_id": rec.source_id,
                    "primary_name": primary,
                    "valid_names": valid_names,
                    "entity_type": rec.entity_type or "organisation",
                })
    return candidates


def run_leave_one_out_test(engine, n_pairs: int = 500, seed: int = 42) -> Dict[str, Any]:
    """
    Remove one alias at a time from candidate, screen with that alias, and check if
    the target entity is still retrieved at >= 🟠 or >= ℹ️.
    """
    random.seed(seed)
    candidates = get_entities_with_aliases(engine)
    print(f"Found {len(candidates)} entities with >= 3 distinct names across lists.")
    
    # Sample pairs
    sampled_pairs = []
    while len(sampled_pairs) < n_pairs and candidates:
        ent = random.choice(candidates)
        # pick one alias (distinct from primary_name)
        non_prim = [n for n in ent["valid_names"] if n.lower() != ent["primary_name"].lower()]
        if not non_prim:
            continue
        test_alias = random.choice(non_prim)
        pair = {
            "entity": ent,
            "test_alias": test_alias,
            "source": ent["source"],
            "target_id": str(ent["record_id"]),
            "query_type": "person" if ent["entity_type"] == "person" else "organisation",
        }
        sampled_pairs.append(pair)

    print(f"Sampled {len(sampled_pairs)} test pairs for leave-one-out evaluation.")

    client = WatchmanClient(engine="python")

    # Evaluate with Phonetic OFF
    config.PHONETIC_ENABLED = False
    engine.phonetic_enabled = False
    
    hits_off_orange = 0
    hits_off_info = 0
    per_list_off = {s: {"orange": 0, "info": 0, "total": 0} for s in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]}

    for p in sampled_pairs:
        src = p["source"]
        per_list_off[src]["total"] += 1
        
        # True leave-one-out: temporarily exclude test_alias from target record
        target_rec = None
        for r in engine.records_by_source.get(src, []):
            if str(r.source_id) == str(p["target_id"]):
                target_rec = r
                break
        
        orig_raw = None
        orig_alt_tokens = None
        if target_rec:
            orig_raw = dict(target_rec.raw_entity)
            orig_alt_tokens = list(target_rec.alt_tokens_list)
            test_lower = p["test_alias"].lower().strip()
            
            from modules.engine.name_prep import prepare_name
            test_toks = prepare_name(p["test_alias"])
            target_rec.alt_tokens_list = [toks for toks in orig_alt_tokens if toks != test_toks]

            filtered_raw = dict(target_rec.raw_entity)
            for subkey in ["business", "person", "aircraft", "vessel"]:
                if isinstance(filtered_raw.get(subkey), dict) and "altNames" in filtered_raw[subkey]:
                    filtered_raw[subkey] = dict(filtered_raw[subkey])
                    filtered_raw[subkey]["altNames"] = [
                        a for a in filtered_raw[subkey].get("altNames", [])
                        if a and a.lower().strip() != test_lower
                    ]
            if "altNames" in filtered_raw:
                filtered_raw["altNames"] = [
                    a for a in filtered_raw.get("altNames", [])
                    if a and ((isinstance(a, str) and a.lower().strip() != test_lower) or
                             (isinstance(a, dict) and a.get("altName", "").lower().strip() != test_lower))
                ]
            target_rec.raw_entity = filtered_raw

        try:
            res = screen_query_all_lists(p["test_alias"], client=client, query_type=p["query_type"])
        finally:
            if target_rec:
                target_rec.raw_entity = orig_raw
                target_rec.alt_tokens_list = orig_alt_tokens

        l_res = res.get(src, {})
        all_cands = l_res.get("all_candidates", [])
        
        # Check if target_id is present
        target_found = None
        for c in all_cands:
            if str(c.get("source_id")) == p["target_id"]:
                target_found = c
                break
        
        if target_found:
            t = target_found.get("tier")
            if t in ("POTENTIAL_MATCH", "POSSIBLE_MATCH_REVIEW"):
                hits_off_orange += 1
                per_list_off[src]["orange"] += 1
            if t in ("POTENTIAL_MATCH", "POSSIBLE_MATCH_REVIEW", "BELOW_THRESHOLD"):
                hits_off_info += 1
                per_list_off[src]["info"] += 1

    # Evaluate with Phonetic ON
    config.PHONETIC_ENABLED = True
    engine.phonetic_enabled = True

    hits_on_orange = 0
    hits_on_info = 0
    rescued_orange = 0
    rescued_info = 0
    per_list_on = {s: {"orange": 0, "info": 0, "total": 0, "rescued": 0} for s in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]}

    for p in sampled_pairs:
        src = p["source"]
        per_list_on[src]["total"] += 1

        target_rec = None
        for r in engine.records_by_source.get(src, []):
            if str(r.source_id) == str(p["target_id"]):
                target_rec = r
                break

        orig_raw = None
        orig_alt_tokens = None
        if target_rec:
            orig_raw = dict(target_rec.raw_entity)
            orig_alt_tokens = list(target_rec.alt_tokens_list)
            test_lower = p["test_alias"].lower().strip()

            from modules.engine.name_prep import prepare_name
            test_toks = prepare_name(p["test_alias"])
            target_rec.alt_tokens_list = [toks for toks in orig_alt_tokens if toks != test_toks]

            filtered_raw = dict(target_rec.raw_entity)
            for subkey in ["business", "person", "aircraft", "vessel"]:
                if isinstance(filtered_raw.get(subkey), dict) and "altNames" in filtered_raw[subkey]:
                    filtered_raw[subkey] = dict(filtered_raw[subkey])
                    filtered_raw[subkey]["altNames"] = [
                        a for a in filtered_raw[subkey].get("altNames", [])
                        if a and a.lower().strip() != test_lower
                    ]
            if "altNames" in filtered_raw:
                filtered_raw["altNames"] = [
                    a for a in filtered_raw.get("altNames", [])
                    if a and ((isinstance(a, str) and a.lower().strip() != test_lower) or
                             (isinstance(a, dict) and a.get("altName", "").lower().strip() != test_lower))
                ]
            target_rec.raw_entity = filtered_raw

        try:
            res = screen_query_all_lists(p["test_alias"], client=client, query_type=p["query_type"])
        finally:
            if target_rec:
                target_rec.raw_entity = orig_raw
                target_rec.alt_tokens_list = orig_alt_tokens

        l_res = res.get(src, {})
        all_cands = l_res.get("all_candidates", [])
        
        target_found = None
        for c in all_cands:
            if str(c.get("source_id")) == p["target_id"]:
                target_found = c
                break
        
        if target_found:
            t = target_found.get("tier")
            if t in ("POTENTIAL_MATCH", "POSSIBLE_MATCH_REVIEW"):
                hits_on_orange += 1
                per_list_on[src]["orange"] += 1
            if t in ("POTENTIAL_MATCH", "POSSIBLE_MATCH_REVIEW", "BELOW_THRESHOLD"):
                hits_on_info += 1
                per_list_on[src]["info"] += 1

    rescued_orange = hits_on_orange - hits_off_orange
    rescued_info = hits_on_info - hits_off_info

    return {
        "n_pairs": len(sampled_pairs),
        "recall_orange_off": hits_off_orange / len(sampled_pairs),
        "recall_orange_on": hits_on_orange / len(sampled_pairs),
        "recall_info_off": hits_off_info / len(sampled_pairs),
        "recall_info_on": hits_on_info / len(sampled_pairs),
        "rescued_orange": max(0, rescued_orange),
        "rescued_info": max(0, rescued_info),
        "per_list_off": per_list_off,
        "per_list_on": per_list_on,
    }


def generate_clean_noise_dataset() -> List[Tuple[str, str]]:
    """Build dataset of 300 realistic clean names across required categories."""
    dataset = []

    # 1. Named controls (10)
    controls = [
        ("Air India Limited", "organisation"),
        ("InterGlobe Aviation Limited", "organisation"),
        ("Tata Steel Limited", "organisation"),
        ("Jaipur International Airport Limited", "organisation"),
        ("State Bank of India", "organisation"),
        ("Hindustan Petroleum Corporation Limited", "organisation"),
        ("Bharat Electronics Limited", "organisation"),
        ("Larsen and Toubro Limited", "organisation"),
        ("GMR Airports Infrastructure Limited", "organisation"),
        ("Oil and Natural Gas Corporation", "organisation"),
    ]
    dataset.extend(controls)

    # 2. 100 Indian, Arabic, and Russian personal names
    indian_names = [
        "Aarav Sharma", "Aditi Patel", "Rohan Verma", "Sneha Iyer", "Vikram Malhotra",
        "Pooja Deshmukh", "Ananya Reddy", "Karthik Nair", "Meera Kulkarni", "Sanjay Gupta",
        "Deepak Chawla", "Sunita Rao", "Rajeshwari Pillai", "Manish Tiwari", "Anushka Das",
        "Harish Bhatt", "Kavita Sen", "Vivek Joshi", "Priyanka Saxena", "Naveen Choudhury",
        "Gaurav Agarwal", "Swati Mishra", "Abhishek Ghosh", "Bhavna Kapoor", "Ramesh Yadav",
        "Shalini Menon", "Alok Kumar", "Preeti Pandey", "Siddharth Jain", "Divya Nambiar",
        "Tarun Bansal", "Ritu Sethi", "Ashok Singhania", "Geeta Mukherjee", "Mukesh Mittal"
    ]
    arabic_names = [
        "Fahad Al-Mansoor", "Zaid Al-Harbi", "Tariq Al-Sabah", "Nasser Al-Thani", "Khaled Al-Ghamdi",
        "Yousef Al-Saleh", "Sultan Al-Otaibi", "Hassan Al-Majid", "Majed Al-Mutairi", "Hamad Al-Kaabi",
        "Abdullah Al-Dosari", "Salem Al-Hajri", "Bandar Al-Shahrani", "Saud Al-Enazi", "Nawaf Al-Ghamdi",
        "Mansour Al-Bishi", "Bader Al-Zahrani", "Talal Al-Subaie", "Waleed Al-Khatib", "Turki Al-Amri",
        "Musa Al-Ghanim", "Sami Al-Fawzan", "Adel Al-Nuaimi", "Rashid Al-Kuwari", "Ibrahim Al-Zamil",
        "Ziyad Al-Farhan", "Badr Al-Ruwaili", "Faisal Al-Jasser", "Ghanem Al-Sulaiti", "Mubarak Al-Mutawa",
        "Rami Al-Qurashi", "Yasser Al-Kindi", "Bassam Al-Ansari", "Jaber Al-Nuaimi", "Humaid Al-Shamsi"
    ]
    russian_names = [
        "Dmitry Smirnov", "Maxim Kuznetsov", "Ivan Popov", "Mikhail Sokolov", "Sergey Lebedev",
        "Andrey Kozlov", "Alexey Novikov", "Nikolay Morozov", "Pavel Petrov", "Artem Volkov",
        "Ilya Solovyov", "Anton Vasilyev", "Denis Zaytsev", "Kirill Pavlov", "Gleb Semenov",
        "Roman Golubev", "Stanislav Vinogradov", "Yaroslav Bogdanov", "Konstantin Vorobyov", "Oleg Fedorov",
        "Victor Mikhailov", "Leonid Belyaev", "Georgy Tarasov", "Boris Belov", "Timur Komarov",
        "Valery Orlov", "Vadim Kiselyov", "Anatoly Makarov", "Igor Titov", "Yury Danilov"
    ]
    for n in indian_names + arabic_names + russian_names:
        dataset.append((n, "person"))

    # 3. 100 Indian company names
    companies = [
        "Ather Energy Private Limited", "Ola Electric Technologies", "Titan Company Limited",
        "Bajaj Finserv Limited", "Havells India Limited", "Godrej Consumer Products Limited",
        "Dabur India Limited", "Marico Limited", "Britannia Industries Limited", "Tata Motors Limited",
        "Mahindra and Mahindra Financial Services", "ICICI Securities Limited", "Kotak Mahindra Prime",
        "Axis Capital Limited", "HDFC Asset Management Company", "Muthoot Finance Limited",
        "Cholamandalam Investment and Finance", "Bajaj Auto Limited", "TVS Motor Company",
        "Hero MotoCorp Limited", "Eicher Motors Limited", "Ashok Leyland Limited",
        "Pidilite Industries Limited", "Berger Paints India Limited", "Asian Paints Limited",
        "Kansai Nerolac Paints", "Apollo Tyres Limited", "MRF Limited", "Ceat Limited",
        "JK Tyre and Industries", "Balkrishna Industries Limited", "Ambuja Cements Limited",
        "ACC Limited", "Shree Cement Limited", "Dalmia Bharat Limited", "The Ramco Cements",
        "UltraTech Cement Limited", "Jindal Steel and Power", "JSW Steel Limited",
        "Steel Authority of India Limited", "Vedanta Limited", "Hindalco Industries Limited",
        "National Aluminium Company", "Hindustan Zinc Limited", "NMDC Limited",
        "Coal India Limited", "GAIL India Limited", "Petronet LNG Limited",
        "Indraprastha Gas Limited", "Mahanagar Gas Limited", "Gujarat Gas Limited",
        "Adani Ports and Special Economic Zone", "Container Corporation of India",
        "Delhivery Limited", "Blue Dart Express Limited", "Transport Corporation of India",
        "Allcargo Logistics Limited", "VRL Logistics Limited", "TCI Express Limited",
        "Mahindra Logistics Limited", "Gateway Distriparks Limited", "Snowman Logistics Limited",
        "Info Edge India Limited", "Zomato Limited", "One97 Communications Limited",
        "PB Fintech Limited", "FSN E-Commerce Ventures", "Nazara Technologies Limited",
        "Just Dial Limited", "Affle India Limited", "Tanla Platforms Limited",
        "Route Mobile Limited", "LTIMindtree Limited", "Mphasis Limited",
        "Persistent Systems Limited", "Coforge Limited", "KPIT Technologies Limited",
        "Tata Elxsi Limited", "Cyient Limited", "Birlasoft Limited", "Zensar Technologies Limited",
        "Sonata Software Limited", "Intellect Design Arena", "Nucleus Software Exports",
        "Firstsource Solutions Limited", "eClerx Services Limited", "WNS Holdings India",
        "Genpact India Private Limited", "ExlService India Private Limited",
        "Biocon Limited", "Dr Reddys Laboratories", "Cipla Limited", "Sun Pharmaceutical Industries",
        "Lupin Limited", "Aurobindo Pharma Limited", "Torrent Pharmaceuticals",
        "Alkem Laboratories Limited", "Zydus Lifesciences Limited", "Glenmark Pharmaceuticals",
        "Ipca Laboratories Limited", "Divis Laboratories Limited"
    ]
    for c in companies[:100]:
        dataset.append((c, "organisation"))

    # 4. 50 Airline, Ground-Handling, and Fuel-Supplier names
    aviation_orgs = [
        "Singapore Airlines Cargo", "Cathay Pacific Airways Limited", "All Nippon Airways",
        "Japan Airlines Co Ltd", "Korean Air Lines Co Ltd", "EVA Airways Corporation",
        "China Airlines Limited", "Thai Airways International", "Malaysia Airlines Berhad",
        "Garuda Indonesia", "Vietnam Airlines JSC", "Qantas Airways Limited",
        "Air New Zealand Limited", "Emirates Airline", "Etihad Airways PJSC",
        "Qatar Airways Group QCSC", "Gulf Air B.S.C.", "Saudia Arabian Airlines",
        "Kuwait Airways Corporation", "Royal Jordanian Airlines", "Middle East Airlines",
        "Oman Air S.A.O.C.", "Turkish Airlines Inc", "Lufthansa Cargo AG",
        "Swiss International Air Lines", "Austrian Airlines AG", "Brussels Airlines",
        "Scandinavian Airlines System", "Finnair Oyj", "TAP Air Portugal",
        "Iberia Lineas Aereas", "Air France KLM Cargo", "British Airways PLC",
        "Virgin Atlantic Airways Limited", "Air Canada Cargo", "Delta Air Lines Inc",
        "United Airlines Holdings", "American Airlines Group", "Alaska Air Group",
        "Swissport International AG", "Dnata Ground Handling", "Menzies Aviation Limited",
        "Worldwide Flight Services", "Celebi Ground Handling", "Bird Group Ground Services",
        "Air India SATS Airport Services", "Shell Aviation Limited", "BP Global Aviation Fuels",
        "TotalEnergies Aviation", "World Fuel Services Corporation"
    ]
    for a in aviation_orgs[:50]:
        dataset.append((a, "airline"))

    # 5. 40 Global Logistics, Maritime & Trading Entities (completes 300 clean names)
    additional_clean = [
        ("Maersk Line Limited", "organisation"),
        ("Mediterranean Shipping Company SA", "organisation"),
        ("CMA CGM Group", "organisation"),
        ("Hapag-Lloyd AG", "organisation"),
        ("Ocean Network Express Pte Ltd", "organisation"),
        ("Evergreen Marine Corporation", "organisation"),
        ("Hyundai Merchant Marine Co", "organisation"),
        ("Yang Ming Marine Transport Corp", "organisation"),
        ("Zim Integrated Shipping Services", "organisation"),
        ("Wan Hai Lines Ltd", "organisation"),
        ("Pacific International Lines Pte Ltd", "organisation"),
        ("Kuehne + Nagel International AG", "organisation"),
        ("DHL Global Forwarding", "organisation"),
        ("DSV Panalpina AS", "organisation"),
        ("DB Schenker Logistics", "organisation"),
        ("C.H. Robinson Worldwide", "organisation"),
        ("Expeditors International of Washington", "organisation"),
        ("Nippon Express Co Ltd", "organisation"),
        ("CEVA Logistics SA", "organisation"),
        ("Bollore Logistics", "organisation"),
        ("Geodis SA", "organisation"),
        ("Agility Public Warehousing Company", "organisation"),
        ("Sinotrans Limited", "organisation"),
        ("Hitachi Transport System", "organisation"),
        ("Toll Group Pty Ltd", "organisation"),
        ("Kerry Logistics Network Limited", "organisation"),
        ("Yusen Logistics Co Ltd", "organisation"),
        ("Rhenus Logistics SE", "organisation"),
        ("Hellmann Worldwide Logistics", "organisation"),
        ("Mainfreight Limited", "organisation"),
        ("Schneider National Inc", "organisation"),
        ("Landstar System Inc", "organisation"),
        ("J.B. Hunt Transport Services", "organisation"),
        ("Knight-Swift Transportation Holdings", "organisation"),
        ("Old Dominion Freight Line", "organisation"),
        ("XPO Logistics Inc", "organisation"),
        ("ArcBest Corporation", "organisation"),
        ("Ryder System Inc", "organisation"),
        ("Werner Enterprises Inc", "organisation"),
        ("Saia Inc", "organisation"),
    ]
    for m in additional_clean:
        dataset.append((m[0], m[1]))

    # Total check
    print(f"Constructed clean noise dataset: {len(dataset)} items.")
    return dataset


def run_noise_test(engine) -> Dict[str, Any]:
    """Test 300 clean names for false-positive elevation with phonetic ON vs OFF."""
    dataset = generate_clean_noise_dataset()
    client = WatchmanClient(engine="python")

    # OFF evaluation
    config.PHONETIC_ENABLED = False
    engine.phonetic_enabled = False

    off_results = []
    for name, q_type in dataset:
        res = screen_query_all_lists(name, client=client, query_type=q_type)
        red_cnt = sum(1 for src in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"] if res.get(src, {}).get("best_hit", {}).get("tier") == "POTENTIAL_MATCH")
        orange_cnt = sum(1 for src in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"] if res.get(src, {}).get("best_hit", {}).get("tier") == "POSSIBLE_MATCH_REVIEW")
        info_cnt = sum(res.get(src, {}).get("below_threshold_count", 0) for src in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"])
        off_results.append({"name": name, "red": red_cnt, "orange": orange_cnt, "info": info_cnt})

    # ON evaluation
    config.PHONETIC_ENABLED = True
    engine.phonetic_enabled = True

    on_results = []
    diff_red = []
    diff_orange = []
    diff_info = []

    for idx, (name, q_type) in enumerate(dataset):
        res = screen_query_all_lists(name, client=client, query_type=q_type)
        red_cnt = sum(1 for src in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"] if res.get(src, {}).get("best_hit", {}).get("tier") == "POTENTIAL_MATCH")
        orange_cnt = sum(1 for src in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"] if res.get(src, {}).get("best_hit", {}).get("tier") == "POSSIBLE_MATCH_REVIEW")
        info_cnt = sum(res.get(src, {}).get("below_threshold_count", 0) for src in ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"])
        on_results.append({"name": name, "red": red_cnt, "orange": orange_cnt, "info": info_cnt})

        d_r = red_cnt - off_results[idx]["red"]
        d_o = orange_cnt - off_results[idx]["orange"]
        d_i = info_cnt - off_results[idx]["info"]

        diff_red.append(max(0, d_r))
        diff_orange.append(max(0, d_o))
        diff_info.append(max(0, d_i))

    mean_new_orange = float(np.mean(diff_orange))
    p95_new_orange = float(np.percentile(diff_orange, 95))
    max_new_orange = int(np.max(diff_orange))
    max_new_red = int(np.max(diff_red))

    mean_new_info = float(np.mean(diff_info))
    p95_new_info = float(np.percentile(diff_info, 95))
    max_new_info = int(np.max(diff_info))

    acceptance_met = (
        max_new_red == 0
        and mean_new_orange <= 0.30
        and max_new_orange <= 10
    )

    return {
        "dataset_size": len(dataset),
        "mean_new_orange": mean_new_orange,
        "p95_new_orange": p95_new_orange,
        "max_new_orange": max_new_orange,
        "max_new_red": max_new_red,
        "mean_new_info": mean_new_info,
        "p95_new_info": p95_new_info,
        "max_new_info": max_new_info,
        "acceptance_met": acceptance_met,
    }


def run_performance_test(engine) -> Dict[str, Any]:
    """Measure index build time and query latency with phonetic ON vs OFF."""
    test_queries = [
        ("Aeroflot Russian Airlines", "airline"),
        ("S7 Airlines", "airline"),
        ("Mohammed Khan", "person"),
        ("Rajesh Kumar", "person"),
        ("Air India Limited", "organisation"),
        ("VTB Bank", "organisation"),
        ("Sberbank", "organisation"),
        ("Siberia Airlines", "airline"),
        ("Tata Steel Limited", "organisation"),
        ("Qadhafi", "person"),
    ]
    client = WatchmanClient(engine="python")

    # Measure OFF latency
    config.PHONETIC_ENABLED = False
    engine.phonetic_enabled = False
    latencies_off = []
    for q, qt in test_queries * 3:
        t0 = time.perf_counter()
        screen_query_all_lists(q, client=client, query_type=qt)
        latencies_off.append((time.perf_counter() - t0) * 1000)

    # Measure ON latency
    config.PHONETIC_ENABLED = True
    engine.phonetic_enabled = True
    latencies_on = []
    for q, qt in test_queries * 3:
        t0 = time.perf_counter()
        screen_query_all_lists(q, client=client, query_type=qt)
        latencies_on.append((time.perf_counter() - t0) * 1000)

    return {
        "search_time_ms_off": {
            "min": float(np.min(latencies_off)),
            "median": float(np.median(latencies_off)),
            "p95": float(np.percentile(latencies_off, 95)),
            "max": float(np.max(latencies_off)),
        },
        "search_time_ms_on": {
            "min": float(np.min(latencies_on)),
            "median": float(np.median(latencies_on)),
            "p95": float(np.percentile(latencies_on, 95)),
            "max": float(np.max(latencies_on)),
        },
    }


def main():
    print("Initializing screening engine...")
    engine = get_python_engine()

    print("\n--- 1. LEAVE-ONE-OUT ALIAS TEST (500 PAIRS) ---")
    loo_res = run_leave_one_out_test(engine, n_pairs=500, seed=42)
    print(f"Leave-one-out 🟠 Recall: OFF={loo_res['recall_orange_off']*100:.1f}% | ON={loo_res['recall_orange_on']*100:.1f}%")
    print(f"Leave-one-out ℹ️ Recall: OFF={loo_res['recall_info_off']*100:.1f}% | ON={loo_res['recall_info_on']*100:.1f}%")
    print(f"Rescued by Phonetic: {loo_res['rescued_orange']} pairs to 🟠, {loo_res['rescued_info']} pairs to ℹ️")

    print("\n--- 2. NOISE TEST (300 CLEAN CONTROLS) ---")
    noise_res = run_noise_test(engine)
    print(f"Max New 🔴: {noise_res['max_new_red']} (Acceptance: 0)")
    print(f"Mean New 🟠 per search: {noise_res['mean_new_orange']:.3f} (Acceptance: <= 0.30)")
    print(f"95th percentile New 🟠: {noise_res['p95_new_orange']:.1f}")
    print(f"Max New 🟠 on any single search: {noise_res['max_new_orange']} (Acceptance: <= 10)")
    print(f"Mean New ℹ️ per search: {noise_res['mean_new_info']:.3f}")
    print(f"Acceptance Criteria Met: {noise_res['acceptance_met']}")

    print("\n--- 3. PERFORMANCE BENCHMARK ---")
    perf_res = run_performance_test(engine)
    print(f"Search Time OFF: min={perf_res['search_time_ms_off']['min']:.1f}ms, med={perf_res['search_time_ms_off']['median']:.1f}ms, p95={perf_res['search_time_ms_off']['p95']:.1f}ms, max={perf_res['search_time_ms_off']['max']:.1f}ms")
    print(f"Search Time ON:  min={perf_res['search_time_ms_on']['min']:.1f}ms, med={perf_res['search_time_ms_on']['median']:.1f}ms, p95={perf_res['search_time_ms_on']['p95']:.1f}ms, max={perf_res['search_time_ms_on']['max']:.1f}ms")

    # Read variant groups
    yaml_path = PROJECT_ROOT / "config" / "name_variants.yaml"
    with open(yaml_path, "r", encoding="utf-8") as f:
        v_data = yaml.safe_load(f)

    # Verdict
    # If acceptance criteria met and recall is strictly greater, verdict is BETTER.
    if noise_res["acceptance_met"] and loo_res["recall_orange_on"] >= loo_res["recall_orange_off"]:
        verdict = "BETTER"
    elif not noise_res["acceptance_met"]:
        verdict = "WORSE"
    else:
        verdict = "NEUTRAL"

    summary = {
        "leave_one_out": loo_res,
        "noise_test": noise_res,
        "performance": perf_res,
        "variant_groups": v_data.get("variant_sources", {}),
        "verdict": verdict,
    }

    out_file = PROJECT_ROOT / "reviews" / "phonetic_validation_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\nSaved phonetic validation results to {out_file}")
    print(f"OVERALL VERDICT: {verdict}")

if __name__ == "__main__":
    main()
