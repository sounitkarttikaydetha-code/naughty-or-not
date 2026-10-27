import urllib.request
import re

def check_mha():
    url = 'https://www.mha.gov.in/index.php/counter-terrorism-counter-radicalization-division'
    req = urllib.request.Request(url, headers={'User-Agent': 'ClearanceCheck/1.1.2 (+compliance contact)'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode('utf-8', errors='ignore')
            print('MHA CTCR status:', r.status)
            for m in re.finditer(r'href=["\']([^"\']*(?:schedule|terrorist|banned|unlawful)[^"\']*)["\']', html, re.I):
                print('MHA link:', m.group(1))
    except Exception as e:
        print('MHA error:', e)

def check_nia():
    url = 'https://nia.mha.gov.in'
    req = urllib.request.Request(url, headers={'User-Agent': 'ClearanceCheck/1.1.2 (+compliance contact)'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            print('NIA status:', r.status)
    except Exception as e:
        print('NIA error:', e)

def check_bis_aircraft():
    url = 'https://www.bis.gov/commercial-and-private-aircraft'
    req = urllib.request.Request(url, headers={'User-Agent': 'ClearanceCheck/1.1.2 (+compliance contact)'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode('utf-8', errors='ignore')
            print('BIS landing status:', r.status)
            for m in re.finditer(r'href=["\']([^"\']*\.pdf)["\']', html, re.I):
                print('BIS PDF link:', m.group(1))
    except Exception as e:
        print('BIS error:', e)

def check_faa():
    url = 'https://www.faa.gov/about/initiatives/iasa'
    req = urllib.request.Request(url, headers={'User-Agent': 'ClearanceCheck/1.1.2 (+compliance contact)'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode('utf-8', errors='ignore')
            print('FAA landing status:', r.status)
            for m in re.finditer(r'href=["\']([^"\']*\.pdf)["\']', html, re.I):
                print('FAA PDF link:', m.group(1))
    except Exception as e:
        print('FAA error:', e)

print('--- Testing MHA & NIA ---')
check_mha()
check_nia()
print('\n--- Testing BIS Aircraft ---')
check_bis_aircraft()
print('\n--- Testing FAA IASA ---')
check_faa()

def find_bis_aircraft():
    candidates = [
        'https://www.bis.gov/index.php/policy-guidance/country-guidance/russia-belarus/commercial-and-private-aircraft',
        'https://www.bis.gov/policy-guidance/country-guidance/russia-belarus/commercial-and-private-aircraft',
        'https://www.bis.gov/russia-belarus-aircraft',
        'https://www.bis.doc.gov/index.php/policy-guidance/country-guidance/russia-belarus',
    ]
    for c in candidates:
        try:
            req = urllib.request.Request(c, headers={'User-Agent': 'ClearanceCheck/1.1.2 (+compliance contact)'})
            with urllib.request.urlopen(req, timeout=10) as r:
                print('Candidate SUCCESS:', c, r.status)
                html = r.read().decode('utf-8', errors='ignore')
                for m in re.finditer(r'href=["\']([^"\']*\.pdf)["\']', html):
                    print('  PDF:', m.group(1))
        except Exception as e:
            print('Candidate failed:', c, e)

print('\n--- Finding BIS Aircraft URL ---')
find_bis_aircraft()

def check_un_date():
    url = 'https://scsanctions.un.org/resources/xml/en/consolidated.xml'
    req = urllib.request.Request(url, headers={'User-Agent': 'ClearanceCheck/1.1.2 (+compliance contact)'})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            chunk = r.read(1024).decode('utf-8', errors='ignore')
            m = re.search(r'dateGenerated=["\']([^"\']+)["\']', chunk)
            if m:
                print('Live UN dateGenerated:', m.group(1))
    except Exception as e:
        print('UN Error:', e)

print('\n--- Testing UN Live dateGenerated ---')
check_un_date()
