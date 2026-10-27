import urllib.request
import re

url = 'https://www.bis.doc.gov/index.php/policy-guidance/country-guidance/sanctions-regulations/13-policy-guidance/country-guidance/russia-belarus/2988-bis-list-of-commercial-and-private-aircraft-in-potential-violation-of-the-export-administration-regulations-ear'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode('utf-8', errors='replace')
        print(f"Loaded BIS Aircraft page. len={len(html)}")
        links = re.findall(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.DOTALL)
        for h, t in links:
            if 'aircraft' in h.lower() or 'aircraft' in t.lower() or 'potential' in h.lower():
                print(f"{t.strip()[:40]} -> {h}")
except Exception as e:
    print("Error:", e)
