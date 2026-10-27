import urllib.request
import re

url = 'https://scsanctions.un.org/resources/xml/en/consolidated.xml'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=15) as resp:
    chunk = resp.read(2000)
    text = chunk.decode('utf-8', errors='replace')
    m = re.search(r'dateGenerated="([^"]+)"', text)
    if m:
        print('Live UN dateGenerated:', m.group(1))
