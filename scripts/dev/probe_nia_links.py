import sys
import urllib.request
import re

sys.stdout.reconfigure(encoding='utf-8')

url = 'https://nia.mha.gov.in/banned-terrorist-organisations'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=10) as resp:
    html = resp.read().decode('utf-8', errors='replace')
    links = re.findall(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.DOTALL)
    for h, t in links:
        t_clean = re.sub(r'<[^>]+>', '', t).strip()
        if any(w in t_clean.lower() or w in h.lower() for w in ['banned', 'terrorist', 'unlawful', 'pdf', 'schedule']):
            print(f"{t_clean[:55]:55} -> {h}")
