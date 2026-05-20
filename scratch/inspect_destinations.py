import sqlite3

conn = sqlite3.connect('inbound.db')
cursor = conn.cursor()

# Get unique destinations from feishu_raw_data
cursor.execute("SELECT DISTINCT destination FROM feishu_raw_data ORDER BY destination")
feishu_dirs = [r[0] for r in cursor.fetchall()]
print("Feishu destinations:", feishu_dirs)

# Get unique destin_name from gofo_center_collect_stats
cursor.execute("SELECT DISTINCT destin_name FROM gofo_center_collect_stats ORDER BY destin_name")
gofo_dirs = [r[0] for r in cursor.fetchall()]
print("Gofo destin_name:", gofo_dirs)

conn.close()
