import sqlite3

# 连接到数据库
conn = sqlite3.connect('inbound.db')

# 查看一些示例数据
cur = conn.execute('SELECT id, created_at, time_slot FROM inbound_records LIMIT 5')
rows = cur.fetchall()
print('示例数据:')
for row in rows:
    print(row)

conn.close()