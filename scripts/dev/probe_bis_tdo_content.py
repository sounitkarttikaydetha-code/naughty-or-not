import urllib.request
import re

url = 'https://www.bis.doc.gov/index.php/enforcement/oee/export-violations'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=10) as r:
    html = r.read().decode('utf-8', errors='replace')
    print('Length:', len(html))
    # Find all date patterns
    dates = re.findall(r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+202[56]', html, re.IGNORECASE)
    print('Dates found count:', len(dates))
    print('Recent dates:', sorted(set(dates))[-15:])
    
    # Also find any mentions of airlines like Aeroflot, Rossiya, Pobeda, Ural, S7, Belavia
    for airline in ['Aeroflot', 'Rossiya', 'Pobeda', 'Ural', 'Siberia', 'Belavia', 'Nordwind']:
        matches = [m.start() for m in re.finditer(airline, html, re.I)]
        if matches:
            print(f"Found {airline}: {len(matches)} times")
            for idx in matches[:2]:
                snippet = html[max(0, idx-50):min(len(html), idx+200)]
                print(f"  Snippet: {re.sub(r'<[^>]+>', ' ', snippet)}")
