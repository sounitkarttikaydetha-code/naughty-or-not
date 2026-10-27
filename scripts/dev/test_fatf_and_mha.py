import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from modules.fatf.republication import parse_hm_treasury_fixture, cross_check_fatf_sources, evaluate_republication_lag

sys.stdout.reconfigure(encoding='utf-8')

res = parse_hm_treasury_fixture()
print('FATF statement date:', res['statement_date'])
print('Attribution:', res['attribution'])
print('Black list count:', len(res['black_list']), res['black_list'])
print('Grey list count:', len(res['grey_list']), res['grey_list'])
assert len(res['black_list']) == 3, f"Expected 3, got {len(res['black_list'])}"
assert len(res['grey_list']) == 22, f"Expected 22, got {len(res['grey_list'])}"
print('FATF parser check PASSED!')

from modules.india.mha_discovery import parse_ctcr_fixture, get_nia_mirror_entry, check_egazette_notifications
links = parse_ctcr_fixture()
print('CTCR links discovered:', links)
assert 'first_schedule' in links
assert 'fourth_schedule' in links
assert 'unlawful_associations' in links
nia = get_nia_mirror_entry('first_schedule')
print('NIA mirror:', nia)
notif_flag = check_egazette_notifications('2026-09-15')
print('eGazette flag:', notif_flag)
assert 'UAPA notification after our copy' in notif_flag
print('MHA discovery check PASSED!')
