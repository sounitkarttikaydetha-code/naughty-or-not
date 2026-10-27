import urllib.request
import re

url = 'https://www.mha.gov.in/index.php/counter-terrorism-counter-radicalization-division'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=10) as resp:
    html = resp.read().decode('utf-8', errors='replace')

start_idx = html.find('List of Banned Organisations/Individuals')
sub = html[start_idx:start_idx+20000]

blocks = re.findall(r'<div class="documentRecordTitle">(.*?)</div>.*?<div class="viewButton">\s*<a href="([^"]+)"', sub, re.DOTALL)
for title, link in blocks:
    t_clean = re.sub(r'<[^>]+>', ' ', title).strip()
    print(f"TITLE: {t_clean}\nLINK: {link}\n")
