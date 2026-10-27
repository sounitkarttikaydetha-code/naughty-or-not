import urllib.request
import re

url = 'https://www.bis.gov/search?keywords=aircraft'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        html = r.read().decode('utf-8', errors='replace')
        print('Status 200, len:', len(html))
        for m in re.finditer(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.I):
            href, txt = m.group(1), re.sub(r'<[^>]+>', '', m.group(2)).strip()
            if 'aircraft' in href.lower() or 'aircraft' in txt.lower() or 'potential violation' in txt.lower():
                print(f"{txt[:50]} -> {href}")
except Exception as e:
    print('Search error:', e)
