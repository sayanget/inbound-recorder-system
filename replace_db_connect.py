import re

# 读取文件
with open('single_app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 统计替换次数
count = content.count('sqlite3.connect(DB_PATH)')
print(f'Found {count} occurrences of sqlite3.connect(DB_PATH)')

# 替换
new_content = content.replace('sqlite3.connect(DB_PATH)', 'get_db()')

# 写回文件
with open('single_app.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f'Replaced {count} occurrences')
