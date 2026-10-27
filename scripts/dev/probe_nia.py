import sys
import urllib.request
import re

sys.stdout.reconfigure(encoding='utf-8')

url = 'https://nia.mha.gov.in'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        html = resp.read().decode('utf-8', errors='replace')
        print(f"NIA loaded. len={len(html)}")
        links = re.findall(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.DOTALL | re.IGNORECASE)
        for href, text in links:
            t = re.sub(r'\s+', ' ', text).strip()
            if any(k in t.lower() or k in href.lower() for k in ['banned', 'terrorist', 'unlawful', 'schedule']):
                print(f"NIA LINK: {t:40} -> {href}")
except Exception as e:
    print("NIA error:", e)
