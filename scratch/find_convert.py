with open('single_app.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for idx, line in enumerate(lines):
    if 'convert_query_placeholders' in line:
        print(f"Line {idx+1}: {line.strip()}")
