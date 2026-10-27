import urllib.request
import json
from pathlib import Path

url = 'https://www.gov.uk/api/content/government/publications/money-laundering-advisory-notice-high-risk-third-countries--2/money-laundering-advisory-notice-high-risk-third-countries--2'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        out_path = Path('tests/fixtures/hm_treasury_fatf_june_2026.json')
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Saved fixture to {out_path} ({out_path.stat().st_size} bytes)")
except Exception as e:
    print("Error saving fixture:", e)
