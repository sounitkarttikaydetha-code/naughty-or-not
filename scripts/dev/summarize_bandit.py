import json

with open('reviews/bandit_report.json', 'r', encoding='utf-8') as f:
    rep = json.load(f)

totals = rep.get('metrics', {}).get('_totals', {})
results = rep.get('results', [])

print("======================================================================")
print("BANDIT STATIC SECURITY ANALYSIS REPORT")
print("======================================================================")
print(f"Lines of Code Analyzed: {totals.get('loc', 0)}")
print(f"Total Findings: {len(results)}")

by_sev = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
for issue in results:
    sev = issue.get('issue_severity', 'LOW').upper()
    by_sev[sev] = by_sev.get(sev, 0) + 1

print(f"Severity Breakdown: High: {by_sev.get('HIGH', 0)} | Medium: {by_sev.get('MEDIUM', 0)} | Low: {by_sev.get('LOW', 0)}")
print("----------------------------------------------------------------------")
for issue in results:
    print(f"[{issue.get('issue_severity')}] {issue.get('filename')}:{issue.get('line_number')} ({issue.get('test_id')} - {issue.get('test_name')}): {issue.get('issue_text')}")
