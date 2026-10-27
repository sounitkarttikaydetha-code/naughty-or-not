import urllib.request
import re

for path in [
    '/unlawful-associations-section3-unlawful-activities-prevention-act-1967',
    '/individuals-terrorists-fourth-schedule-unlawful-activities-prevention-act',
]:
    url = f"https://www.mha.gov.in{path}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode('utf-8', errors='replace')
            print(f"URL: {url} -> {resp.status}, len={len(html)}")
            # look for table, pdf, json or list items
            rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL | re.IGNORECASE)
            print(f"Table rows found: {len(rows)}")
            if rows:
                print("First row:", re.sub(r'<[^>]+>', ' ', rows[0])[:200])
                if len(rows) > 1:
                    print("Second row:", re.sub(r'<[^>]+>', ' ', rows[1])[:200])
    except Exception as e:
        print(f"URL: {url} -> ERROR: {e}")
