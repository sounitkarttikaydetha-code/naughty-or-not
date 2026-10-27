import urllib.request

urls = [
    "https://www.faa.gov/sites/faa.gov/files/IASAWSR119r.pdf",
    "https://www.faa.gov/sites/faa.gov/files/about/initiatives/iasa/FAA_Initiatives_IASA.pdf",
]
for u in urls:
    req = urllib.request.Request(u, headers={'User-Agent': 'ClearanceCheck/1.1.2 (+compliance contact)'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            print(u, r.status, r.headers.get('Content-Type'), r.headers.get('Last-Modified'))
    except Exception as e:
        print(u, 'Error:', e)
