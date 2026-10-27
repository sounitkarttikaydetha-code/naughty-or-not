import ssl
import socket

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

print("Domain SSL Certificate Issuer Audit:")
print("=" * 60)
for d in domains:
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((d, 443), timeout=7) as sock:
            with ctx.wrap_socket(sock, server_hostname=d) as ssock:
                cert = ssock.getpeercert()
                issuer = dict(x[0] for x in cert.get('issuer', []))
                subject = dict(x[0] for x in cert.get('subject', []))
                org = issuer.get('organizationName', '')
                cn = issuer.get('commonName', '')
                is_emudhra = 'emudhra' in org.lower() or 'emudhra' in cn.lower()
                print(f"{d:26}: OK | Issuer: {org} - {cn} | eMudhra: {is_emudhra}")
    except Exception as e:
        print(f"{d:26}: FAIL | {e}")
