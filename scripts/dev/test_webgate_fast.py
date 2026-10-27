import urllib.request
import re
import time

t0 = time.time()
url = 'https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content?token=dG9rZW4tMjAxNw'
req = urllib.request.Request(url, headers={'User-Agent': 'ClearanceCheck/1.1.2'})
with urllib.request.urlopen(req, timeout=8) as resp:
    data = resp.read(4096)
    elapsed = time.time() - t0
    print(f"Read {len(data)} bytes in {elapsed:.2f}s")
    m = re.search(r'generationDate="([^"]+)"', data.decode('utf-8', errors='replace'))
    if m:
        print('generationDate:', m.group(1))
    else:
        print('First 200 chars:', data[:200])
