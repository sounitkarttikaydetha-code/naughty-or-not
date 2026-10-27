import urllib.request
from pathlib import Path

url = 'https://www.mha.gov.in/index.php/counter-terrorism-counter-radicalization-division'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        html = resp.read().decode('utf-8', errors='replace')
        out_p = Path('tests/fixtures/mha_ctcr_page.html')
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(html, encoding='utf-8')
        print(f"Saved MHA CTCR fixture to {out_p} ({out_p.stat().st_size} bytes)")
except Exception as e:
    print("Error:", e)
