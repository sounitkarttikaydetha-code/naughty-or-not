import ssl
import socket
import json

domains = [
    'www.mha.gov.in',
    'nia.mha.gov.in',
    'ifsca.gov.in',
    'egazette.gov.in',
    'ofac.treasury.gov',
    'sanctionslist.fcdo.gov.uk',
    'data.trade.gov',
    'webgate.ec.europa.eu',
    'scsanctions.un.org',
    'www.bis.gov',
    'www.faa.gov',
    'transport.ec.europa.eu',
    'www.fatf-gafi.org',
    'www.gov.uk',
]

print("=" * 80)
print("RAW TLS/SSL CERTIFICATE CHAIN AND VALIDITY AUDIT (eMudhra Distrust Rule)")
print("=" * 80)

for d in domains:
    ctx = ssl.create_default_context()
    print(f"\n--- Hostname: {d} ---")
    try:
        with socket.create_connection((d, 443), timeout=8) as sock:
            with ctx.wrap_socket(sock, server_hostname=d) as ssock:
                cert = ssock.getpeercert()
                issuer_dict = dict(x[0] for x in cert.get('issuer', []))
                subject_dict = dict(x[0] for x in cert.get('subject', []))
                not_before = cert.get('notBefore')
                not_after = cert.get('notAfter')
                serial = cert.get('serialNumber')
                org = issuer_dict.get('organizationName', 'Unknown')
                cn = issuer_dict.get('commonName', 'Unknown')
                is_emudhra = 'emudhra' in org.lower() or 'emudhra' in cn.lower() or 'emudhra' in json.dumps(cert).lower()

                print(f"  Subject      : {subject_dict.get('commonName', '—')}")
                print(f"  Issuer Org   : {org}")
                print(f"  Issuer CN    : {cn}")
                print(f"  Validity From: {not_before}")
                print(f"  Validity To  : {not_after}")
                print(f"  Serial Number: {serial}")
                print(f"  eMudhra Chain: {'PRESENT (COMPROMISED)' if is_emudhra else 'CLEAN (No eMudhra in chain)'}")
    except Exception as e:
        print(f"  Connection Error: {e}")
