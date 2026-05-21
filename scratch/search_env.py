import os

# Read .env file if exists
if os.path.exists('.env'):
    print("--- .env file ---")
    with open('.env', 'r', encoding='utf-8') as f:
        print(f.read())

# Search other files
search_dir = '.'
keyword = 'GOFO_TMS_SHUTTLE_DAY_START_HOUR'
for root, dirs, files in os.walk(search_dir):
    if any(p in root for p in ['.git', '.venv', 'Backups']):
        continue
    for file in files:
        if file.endswith(('.py', '.html', '.js', '.css', '.env', '.example')):
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                if keyword in content:
                    print(f"Found in {path}")
            except Exception:
                pass
