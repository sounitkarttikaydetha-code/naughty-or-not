import urllib.request
import re

url = 'https://www.faa.gov/about/initiatives/iasa'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        html = r.read().decode('utf-8', errors='replace')
        print('Status:', r.status, 'len:', len(html))
        links = re.findall(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.DOTALL)
        for h, t in links:
            if '.pdf' in h.lower() or 'iasa' in h.lower() or 'iasa' in t.lower():
                print(f"{t.strip()[:40]} -> {h}")
except Exception as e:
    print('FAA error:', e)
