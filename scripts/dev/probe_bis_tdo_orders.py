import urllib.request
import re

url = 'https://www.bis.doc.gov/index.php/enforcement/oee/export-violations'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=10) as r:
    html = r.read().decode('utf-8', errors='replace')

for d in ['September', 'October', 'August']:
    for m in re.finditer(rf'({d}\s+\d{{1,2}},?\s+2026)', html, re.I):
        idx = m.start()
        snippet = html[max(0, idx-100):min(len(html), idx+300)]
        print("MATCH:", re.sub(r'<[^>]+>', ' ', snippet).strip())
        print("-" * 50)
