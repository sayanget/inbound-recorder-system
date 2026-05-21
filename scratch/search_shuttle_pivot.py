with open('single_app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if 'shuttle-completed/pivot' in line or 'pivot' in line and 'shuttle' in line:
        print(f"Line {idx+1}: {line.strip()}")
