import sys
import urllib.request
import re

sys.stdout.reconfigure(encoding='utf-8')

urls = [
    'https://nia.mha.gov.in/banned-terrorist-organisations',
    'https://nia.mha.gov.in/en/banned-terrorist-organisations',
    'https://nia.mha.gov.in/individual-terrorists',
    'https://nia.mha.gov.in/declared-unlawful-associations',
]

for url in urls:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"{url} -> {resp.status}")
    except Exception as e:
        print(f"{url} -> {e}")
