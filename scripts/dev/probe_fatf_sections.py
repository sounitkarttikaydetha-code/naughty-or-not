import json

with open('tests/fixtures/hm_treasury_fatf_june_2026.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
body = d['details']['body']
start_im = body.find('id="jurisdictions-under-increased-monitoring"')
start_cfa = body.find('id="high-risk-jurisdictions-subject-to-a-call-for-action"')
start_bg = body.find('id="background-information"')

print('--- Increased Monitoring Section ---')
print(body[start_im:start_cfa])

print('--- Call for Action Section ---')
print(body[start_cfa:start_bg])
