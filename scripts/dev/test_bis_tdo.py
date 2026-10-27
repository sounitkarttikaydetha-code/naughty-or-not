import urllib.request
import re

urls = [
    'https://media.bis.gov/enforcement/export-violations',
    'https://www.bis.gov/enforcement/export-violations',
    'https://www.bis.doc.gov/index.php/enforcement/oee/export-violations',
]

for u in urls:
    try:
        req = urllib.request.Request(u, headers={'User-Agent': 'ClearanceCheck/1.1.2 (+compliance contact)'})
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode('utf-8', errors='ignore')
            print('URL SUCCESS:', u, r.status, len(html))
            # Find 2026 dates
            dates_2026 = re.findall(r'\b(?:Sept(?:ember)?|Oct(?:ober)?|Aug(?:ust)?)\s+\d{1,2},?\s+2026\b', html, re.I)
            print('  2026 dates found:', set(dates_2026[:10]))
            # Find ISO or slash dates
            dates_slash = re.findall(r'\b09/\d{2}/2026\b', html)
            print('  Sept 2026 dates:', set(dates_slash))
            # Look for aeroflot / airline denial orders
            orders = re.findall(r'([^.\n]*?(?:Aeroflot|Siberia|S7|Nordwind|Azur|Pobeda)[^.\n]*?2026[^.\n]*)', html, re.I)
            if orders:
                print('  Order snippets:', orders[:3])
    except Exception as e:
        print('URL failed:', u, e)
