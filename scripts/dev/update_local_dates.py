from pathlib import Path
p = Path("scripts/source_update_check.py")
txt = p.read_text(encoding="utf-8")
txt = txt.replace('"us_ofac": "2026-10-21"', '"us_ofac": "2026-11-09"')
txt = txt.replace('"us_csl": "2026-10-27"', '"us_csl": "2026-11-10"')
txt = txt.replace('"uk_csl": "2026-10-27"', '"uk_csl": "2026-11-03"')
txt = txt.replace('"un_csl": "2026-10-27"', '"un_csl": "2026-11-10"')
p.write_text(txt, encoding="utf-8")
print("Successfully updated LOCAL_COPY_DATES in scripts/source_update_check.py")
