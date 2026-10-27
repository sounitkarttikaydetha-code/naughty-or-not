import urllib.request
import re

url = 'https://www.bis.gov/commercial-and-private-aircraft'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        html = r.read().decode('utf-8', errors='replace')
        print('Status 200, len:', len(html))
        for m in re.finditer(r'href=["\']([^"\']*aircraft[^"\']*)["\']', html, re.I):
            print('Found link:', m.group(1))
except Exception as e:
    print('bis.gov/commercial-and-private-aircraft ->', e)
