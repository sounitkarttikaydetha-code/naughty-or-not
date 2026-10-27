import urllib.request
import re

url = 'https://transport.ec.europa.eu/transport-themes/eu-air-safety-list_en'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode('utf-8', errors='replace')
        print(f"Loaded EU DG MOVE. len={len(html)}")
        links = re.findall(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.DOTALL)
        for h, t in links:
            if '.pdf' in h.lower() or 'safety' in h.lower() or 'air safety' in t.lower():
                print(f"{t.strip()[:40]} -> {h}")
except Exception as e:
    print("Error:", e)
