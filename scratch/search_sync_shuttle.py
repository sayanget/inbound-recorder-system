with open('scripts/sync_tms_shuttle_completed.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if any(k in line for k in ['hour', 'time', '17', '16', '5', '05:', '17:', '16:', 'filter', 'range', 'limit']):
        print(f"Line {idx+1}: {line.strip()}")
