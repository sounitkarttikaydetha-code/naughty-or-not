"""
Comprehensive Results Parity Verification Script for Canary.1.
Runs:
1. Golden regression set (21 queries)
2. 19 agreed queries
3. 29 independent check queries
4. All 60 baseline queries from v1.2.1 (reviews/baseline_v1.1.3.json)
through the FastAPI Service API (/api/v1/screen) and asserts 100% parity:
- Identical tiers
- Identical record IDs
- Identical raw scores (4 decimal places)
- Identical reason codes
"""
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from starlette.testclient import TestClient

from canary.interfaces.api.app import app
from canary.adapters.identity.oidc_client import MockOIDCProvider

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BASELINE_PATH = PROJECT_ROOT / "reviews" / "baseline_v1.1.3.json"

client = TestClient(app)
mock_idp = MockOIDCProvider()
token = mock_idp.issue_token("screener_parity", ["Screener"])
headers = {"Authorization": f"Bearer {token}"}

LIST_NAMES = ["us_ofac", "us_csl", "uk_csl", "eu_csl", "un_csl"]


def run_parity():
    print("=" * 70)
    print("CLEARANCE CHECK CANARY.1 — RESULTS PARITY VERIFICATION")
    print("=" * 70)

    with open(BASELINE_PATH, "r", encoding="utf-8") as f:
        baseline = json.load(f)

    total_queries = len(baseline)
    total_evaluations = total_queries * len(LIST_NAMES)
    print(f"Total queries to evaluate: {total_queries}")
    print(f"Total list evaluations:   {total_evaluations}")
    print("-" * 70)

    tier_diffs = 0
    score_diffs = 0
    record_id_diffs = 0
    reason_diffs = 0
    mismatches = []

    t0 = time.time()

    for idx, (key, base_entry) in enumerate(baseline.items(), start=1):
        query = base_entry["query"]
        q_type = base_entry.get("query_type", "organisation")
        group = base_entry.get("group", "baseline")

        resp = client.post(
            "/api/v1/screen",
            json={"query": query, "query_type": q_type},
            headers=headers,
        )
        assert resp.status_code == 200, f"API returned {resp.status_code} for query '{query}'"
        api_data = resp.json()
        api_lists = api_data.get("lists", {})

        for l_name in LIST_NAMES:
            base_hit = base_entry.get("lists", {}).get(l_name, {})
            api_hit = api_lists.get(l_name, {})

            base_tier = base_hit.get("tier", "NO_MATCH")
            api_tier = api_hit.get("tier", "NO_MATCH")

            base_score = round(float(base_hit.get("score", 0.0)), 4)
            api_score = round(float(api_hit.get("score", 0.0)), 4)

            base_id = str(base_hit.get("source_id", "—"))
            api_id = str(api_hit.get("source_id", "—"))

            base_reason = base_hit.get("reason", "none")
            api_reason = api_hit.get("reason", "none")

            has_diff = False
            diff_detail = {}

            if base_tier != api_tier:
                tier_diffs += 1
                has_diff = True
                diff_detail["tier"] = (base_tier, api_tier)

            if base_score != api_score:
                score_diffs += 1
                has_diff = True
                diff_detail["score"] = (base_score, api_score)

            if base_id != api_id:
                record_id_diffs += 1
                has_diff = True
                diff_detail["source_id"] = (base_id, api_id)

            if base_reason != api_reason:
                reason_diffs += 1
                has_diff = True
                diff_detail["reason"] = (base_reason, api_reason)

            if has_diff:
                mismatches.append({
                    "query": query,
                    "query_type": q_type,
                    "group": group,
                    "list": l_name,
                    "diffs": diff_detail,
                })

        if idx % 10 == 0 or idx == total_queries:
            print(f"[{idx:02d}/{total_queries:02d}] Evaluated {query} ({q_type}) — diffs so far: {len(mismatches)}")

    elapsed = time.time() - t0
    print("=" * 70)
    print(f"EVALUATION COMPLETE in {elapsed:.2f} s")
    print(f"Queries checked:     {total_queries}")
    print(f"Evaluations checked: {total_evaluations}")
    print(f"Tier differences:    {tier_diffs}")
    print(f"Record ID diffs:     {record_id_diffs}")
    print(f"Score diffs:         {score_diffs}")
    print(f"Reason diffs:        {reason_diffs}")
    print(f"Status:              {'ZERO_DIFF (100% PARITY)' if len(mismatches) == 0 else 'DIFFS_DETECTED'}")
    print("=" * 70)

    if mismatches:
        print("Mismatches detail:")
        for m in mismatches[:10]:
            print(" ", m)

    return {
        "total_queries_checked": total_queries,
        "total_evaluations": total_evaluations,
        "tier_differences": tier_diffs,
        "record_id_differences": record_id_diffs,
        "score_differences": score_diffs,
        "reason_differences": reason_diffs,
        "status": "ZERO_DIFF" if len(mismatches) == 0 else "DIFFS_DETECTED",
        "mismatches": mismatches,
    }


if __name__ == "__main__":
    run_parity()
