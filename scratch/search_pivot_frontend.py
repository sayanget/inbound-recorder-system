import os

search_dir = '.'
keyword = 'shuttle-completed/pivot'

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
                    # Print lines containing keyword with context
                    lines = content.splitlines()
                    for idx, line in enumerate(lines):
                        if keyword in line:
                            start = max(0, idx - 5)
                            end = min(len(lines), idx + 6)
                            print(f"--- Context for line {idx+1} in {file} ---")
                            for k in range(start, end):
                                print(f"  {k+1}: {lines[k]}")
            except Exception as e:
                pass
