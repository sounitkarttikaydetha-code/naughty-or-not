import urllib.request

url = "https://www.bis.gov/media/documents/2025.10.10-current-bis-list-commercial-private-aircraft-potential-violation-export-administration"
req = urllib.request.Request(url, headers={'User-Agent': 'ClearanceCheck/1.1.2 (+compliance contact)'})
try:
    with urllib.request.urlopen(req, timeout=10) as r:
        print('Status:', r.status, 'Content-Type:', r.headers.get('Content-Type'))
except Exception as e:
    print('Error:', e)
