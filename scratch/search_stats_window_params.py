with open('static/statistics.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if 'withStatsWindowParams' in line or 'stats_window' in line:
        print(f"Line {idx+1}: {line.strip()}")
