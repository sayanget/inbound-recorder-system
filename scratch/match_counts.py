import sqlite3

conn = sqlite3.connect('inbound.db')
cursor = conn.cursor()

# Get feishu waybills grouped by date and normalized destination
# Normalization:
# - strip .H
# - LAS% -> LAS
# - PHX% -> PHX
# - ATL.G -> ATL
# Let's write a SQL query or do it in Python

cursor.execute("""
    SELECT record_date, destination, SUM(tickets_count)
    FROM feishu_raw_data
    WHERE record_date >= '2026-04-06' AND record_date <= '2026-05-18'
    GROUP BY record_date, destination
""")
feishu_rows = cursor.fetchall()

feishu_map = {}
for r_date, dest, t_cnt in feishu_rows:
    if not dest: continue
    dest = dest.upper().strip()
    if dest.endswith('.H'): dest = dest[:-2]
    if 'LAS' in dest: dest = 'LAS'
    elif 'PHX' in dest: dest = 'PHX'
    elif 'ATL.G' in dest: dest = 'ATL'
    
    key = (r_date, dest)
    feishu_map[key] = feishu_map.get(key, 0) + (t_cnt or 0)

cursor.execute("""
    SELECT record_date, destin_name, SUM(waybill_cnt)
    FROM gofo_center_collect_stats
    WHERE record_date >= '2026-04-06' AND record_date <= '2026-05-18'
    GROUP BY record_date, destin_name
""")
gofo_rows = cursor.fetchall()

gofo_map = {}
for r_date, dest, w_cnt in gofo_rows:
    if not dest: continue
    dest = dest.upper().strip()
    if dest.endswith('.H'): dest = dest[:-2]
    if 'LAS' in dest: dest = 'LAS'
    elif 'PHX' in dest: dest = 'PHX'
    elif 'ATL.G' in dest: dest = 'ATL'
    
    key = (r_date, dest)
    gofo_map[key] = gofo_map.get(key, 0) + (w_cnt or 0)

# Compare and print first 10 differences
all_keys = sorted(list(set(feishu_map.keys()) | set(gofo_map.keys())))
printed = 0
for key in all_keys:
    f_val = feishu_map.get(key, 0)
    g_val = gofo_map.get(key, 0)
    if f_val != g_val:
        diff = f_val - g_val
        print(f"Date: {key[0]}, Dest: {key[1]} | Feishu: {f_val} | Gofo: {g_val} | Diff: {diff}")
        printed += 1
        if printed >= 15:
            break

conn.close()
