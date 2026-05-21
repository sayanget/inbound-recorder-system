import os

search_dir = '.'
keyword = 'is_sorting_active'

for root, dirs, files in os.walk(search_dir):
    if any(p in root for p in ['.git', '.venv', 'Backups']):
        continue
    for file in files:
        if file.endswith(('.py', '.html', '.js', '.css')):
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                if keyword in content:
                    print(f"Found in {path}")
                    # Print lines containing keyword
                    lines = content.splitlines()
                    for idx, line in enumerate(lines):
                        if keyword in line:
                            print(f"  Line {idx+1}: {line.strip()}")
            except Exception as e:
                pass
