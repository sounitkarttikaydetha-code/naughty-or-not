import csv
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

tmp = Path('data/raw/uk_csl.csv.tmp')
with open(tmp, 'r', encoding='utf-8', errors='replace') as f:
    line0 = f.readline().strip()
    print("Line 0:", line0)
    reader = csv.reader(f)
    header = next(reader)
    print("Header columns:", header[:12])
    
    unique_id_idx = header.index('Unique ID') if 'Unique ID' in header else -1
    last_updated_idx = header.index('Last Updated') if 'Last Updated' in header else -1
    date_desig_idx = header.index('Date Designated') if 'Date Designated' in header else -1
    name_idx = header.index('Name 6') if 'Name 6' in header else -1
    print(f"Indices: Unique ID={unique_id_idx}, Last Updated={last_updated_idx}, Date Designated={date_desig_idx}, Name 6={name_idx}")
    
    post_jan_2026 = []
    total_rows = 0
    for row in reader:
        if not row: continue
        total_rows += 1
        desig_date = row[date_desig_idx] if date_desig_idx >= 0 and date_desig_idx < len(row) else ""
        last_up = row[last_updated_idx] if last_updated_idx >= 0 and last_updated_idx < len(row) else ""
        name = row[name_idx] if name_idx >= 0 and name_idx < len(row) else ""
        uid = row[unique_id_idx] if unique_id_idx >= 0 and unique_id_idx < len(row) else ""
        
        # Check if 2026 and month > 01
        for dt_str in [desig_date, last_up]:
            # formats: DD/MM/YYYY or YYYY-MM-DD
            if '/2026' in dt_str or '-2026' in dt_str or '2026-' in dt_str:
                parts = dt_str.split('/')
                if len(parts) == 3 and parts[2] == '2026':
                    m = int(parts[1]) if parts[1].isdigit() else 0
                    if m > 1:
                        post_jan_2026.append((uid, name, desig_date, last_up))
                        break
                elif len(parts) == 3 and parts[0] == '2026':
                    m = int(parts[1]) if parts[1].isdigit() else 0
                    if m > 1:
                        post_jan_2026.append((uid, name, desig_date, last_up))
                        break

    print(f"Total rows scanned: {total_rows}")
    print(f"Designations/Updates made after Jan 2026 found: {len(post_jan_2026)}")
    for item in post_jan_2026[:10]:
        print(" ->", item)
