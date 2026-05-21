with open('scripts/sync_tms_shuttle_completed.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if 'record_date' in line or 'recordDate' in line:
        print(f"Line {idx+1}: {line.strip()}")
