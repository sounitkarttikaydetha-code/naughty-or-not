with open('scripts/dev/run_failsafe_matrix.py', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('elif kind == "bis_tdo":', 'elif kind in ("bis_tdo", "bis_denial_orders"):')
with open('scripts/dev/run_failsafe_matrix.py', 'w', encoding='utf-8') as f:
    f.write(text)
print('Fixed bis_denial_orders check')
