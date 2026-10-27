import urllib.request
import re

url = 'https://www.faa.gov/initiatives/iasa/iasa-program-results'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        html = r.read().decode('utf-8', errors='replace')
        print('Status:', r.status, 'len:', len(html))
        links = re.findall(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.DOTALL)
        for h, t in links:
            if '.pdf' in h.lower() or 'results' in h.lower() or 'category' in t.lower() or 'iasa' in h.lower():
                print(f"{t.strip()[:40]} -> {h}")
except Exception as e:
    print('FAA results error:', e)
