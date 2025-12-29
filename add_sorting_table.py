import sqlite3

# 连接到数据库
conn = sqlite3.connect('inbound.db')
cursor = conn.cursor()

# 创建分拣记录表
cursor.execute("""CREATE TABLE IF NOT EXISTS sorting_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sorting_time DATETIME,
    pieces INTEGER,
    remark TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);""")

conn.commit()
conn.close()

print("分拣记录表创建成功!")