from pathlib import Path

# 1. SPEC.md
spec_p = Path('SPEC.md')
text = spec_p.read_text(encoding='utf-8')
text = text.replace('European Union Consolidated Sanctions List (EEAS)', 'European Union Consolidated Sanctions List (European Commission — DG FISMA)')
text = text.replace('4. `eu_csl` (EU Consolidated List - EEAS)', '4. `eu_csl` (EU Consolidated List - European Commission — DG FISMA)')
old_disc = '  - ⚪ **NOT_CHECKED / DISCARDED (< 0.50 / source unavailable):** ⚪ designates an unavailable source or unverified state; it is never used for "no match".'
new_disc = '  - ⚪ **NOT_CHECKED (Source unavailable):** ⚪ means only that the source could not be checked; candidates below 0.50 are not returned and have no symbol. Never used for "no match".'
text = text.replace(old_disc, new_disc)
text = text.replace('signed PDF compliance dossier', 'PDF compliance dossier')
text = text.replace('~/.clearance_check/import_mappings/', r'%LOCALAPPDATA%\...\import_mappings\\')
spec_p.write_text(text, encoding='utf-8')
print('Updated SPEC.md successfully!')

# 2. docs/dossiers/SYSTEM_DOSSIER_v1.1.1.md
dos_p = Path('docs/dossiers/SYSTEM_DOSSIER_v1.1.1.md')
if dos_p.is_file():
    d_text = dos_p.read_text(encoding='utf-8')
    d_text = d_text.replace('European External Action Service (EEAS)', 'European Commission (DG FISMA)')
    d_text = d_text.replace(
        '- **< 0.50 / Unavailable:** Discarded / Not Checked (⚪). ⚪ designates an unavailable source or unverified state; it is never used for "no match".',
        '- **< 0.50:** Discarded (candidates below 0.50 are not returned and have no symbol). **⚪ NOT_CHECKED:** ⚪ means only that the source could not be checked (unavailable or unverified). Never used for "no match".'
    )
    d_text = d_text.replace('signed PDF compliance dossier', 'PDF compliance dossier')
    d_text = d_text.replace('~/.clearance_check/import_mappings/', r'%LOCALAPPDATA%\...\import_mappings\\')
    dos_p.write_text(d_text, encoding='utf-8')
    print('Updated SYSTEM_DOSSIER_v1.1.1.md successfully!')

# 3. config/ubo_rules.yaml
ubo_p = Path('config/ubo_rules.yaml')
if ubo_p.is_file():
    u_text = ubo_p.read_text(encoding='utf-8')
    u_text = u_text.replace('European External Action Service (EEAS)', 'European Commission (DG FISMA)')
    ubo_p.write_text(u_text, encoding='utf-8')
    print('Updated config/ubo_rules.yaml successfully!')
