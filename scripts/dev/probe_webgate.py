import urllib.request
import re

url = 'https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content?token=dG9rZW4tMjAxNw'
req = urllib.request.Request(url, headers={'User-Agent': 'ClearanceCheck/1.1.2'})
req.add_header('Range', 'bytes=0-4096')
with urllib.request.urlopen(req, timeout=8) as resp:
    data = resp.read()
    print('Read len:', len(data))
    m = re.search(r'generationDate="([^"]+)"', data.decode('utf-8', errors='replace'))
    if m:
        print('generationDate:', m.group(1))
    else:
        print('Not found in chunk! First 300 chars:', data[:300])
