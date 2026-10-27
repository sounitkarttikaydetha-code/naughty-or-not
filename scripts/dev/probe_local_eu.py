import re
from pathlib import Path

for p in [Path('data/raw/eu_csl.xml'), Path('lists/raw/eu_csl.xml')]:
    if p.is_file():
        with open(p, 'rb') as f:
            chunk = f.read(4096)
            m = re.search(r'generationDate="([^"]+)"', chunk.decode('utf-8', errors='replace'))
            print(p, 'generationDate:', m.group(1) if m else 'Not found')
