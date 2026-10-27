import urllib.request
import re
import time

t0 = time.time()
url = 'https://scsanctions.un.org/resources/xml/en/consolidated.xml'
req = urllib.request.Request(url, headers={'User-Agent': 'ClearanceCheck/1.1.2'})
with urllib.request.urlopen(req, timeout=8) as resp:
    data = resp.read(4096)
    elapsed = time.time() - t0
    print(f"Read {len(data)} bytes in {elapsed:.2f}s")
    m = re.search(r'dateGenerated="([^"]+)"', data.decode('utf-8', errors='replace'))
    if m:
        print('dateGenerated:', m.group(1))
    else:
        print('First 200 chars:', data[:200])
