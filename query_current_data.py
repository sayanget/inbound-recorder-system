import sqlite3
import os
from datetime import datetime, timedelta
import pytz

INBOUND_PIECES_ACTUAL_FACTOR = float(os.environ.get("INBOUND_PIECES_ACTUAL_FACTOR", "0.76"))

# 连接数据库
conn = sqlite3.connect('inbound_data.db')
cursor = conn.cursor()

# 获取洛杉矶时区
la_tz = pytz.timezone('America/Los_Angeles')
now_la = datetime.now(la_tz)

# 确定业务日期
if now_la.hour < 5:
    business_date = now_la.date() - timedelta(days=1)
else:
    business_date = now_la.date()

# 计算时间范围
today_start = la_tz.localize(datetime.combine(business_date, datetime.min.time().replace(hour=5)))
next_day_start = today_start + timedelta(days=1)

# 转换为本地时间
today_start_local = today_start.astimezone()
next_day_start_local = next_day_start.astimezone()

print(f'业务日期: {business_date}')
print(f'当前时间: {now_la.strftime("%Y-%m-%d %H:%M:%S")}')
print('=' * 60)

# 查询总车次和总件数
cursor.execute(f'''
    SELECT COUNT(*) as total_vehicles, 
           SUM(CASE 
               WHEN vehicle_type = '53英尺' AND vehicle_no = 'G' THEN 0 
               ELSE ((pieces - COALESCE(excluded_pieces, 0)) * {INBOUND_PIECES_ACTUAL_FACTOR})
           END) as total_pieces 
    FROM inbound_records 
    WHERE created_at >= ? AND created_at < ?
''', (today_start_local.strftime('%Y-%m-%d %H:%M:%S'), 
      next_day_start_local.strftime('%Y-%m-%d %H:%M:%S')))

result = cursor.fetchone()
total_vehicles = result[0] if result else 0
total_pieces = int(round(float(result[1]))) if result and result[1] is not None else 0

# 查询总托盘数
cursor.execute('''
    SELECT SUM(load_amount) as total_pallets
    FROM inbound_records 
    WHERE created_at >= ? AND created_at < ? 
        AND (vehicle_type = '26英尺' OR vehicle_type = '53英尺')
        AND NOT (vehicle_type = '53英尺' AND vehicle_no = 'G')
''', (today_start_local.strftime('%Y-%m-%d %H:%M:%S'), 
      next_day_start_local.strftime('%Y-%m-%d %H:%M:%S')))

result = cursor.fetchone()
total_pallets = int(result[0]) if result[0] else 0

# 查询已分拣件数
cursor.execute('''
    SELECT SUM(pieces) as total_sorted
    FROM sorting_records
    WHERE sorting_time >= ? AND sorting_time < ?
''', (today_start_local.strftime('%Y-%m-%d %H:%M:%S'), 
      next_day_start_local.strftime('%Y-%m-%d %H:%M:%S')))

result = cursor.fetchone()
total_sorted_pieces = int(result[0]) if result[0] else 0

# 按车型统计
cursor.execute(f'''
    SELECT vehicle_type, 
           COUNT(*) as count, 
           SUM(CASE 
               WHEN vehicle_type = '53英尺' AND vehicle_no = 'G' THEN 0 
               ELSE ((pieces - COALESCE(excluded_pieces, 0)) * {INBOUND_PIECES_ACTUAL_FACTOR})
           END) as total_pieces 
    FROM inbound_records 
    WHERE created_at >= ? AND created_at < ?
    GROUP BY vehicle_type
    ORDER BY count DESC
''', (today_start_local.strftime('%Y-%m-%d %H:%M:%S'), 
      next_day_start_local.strftime('%Y-%m-%d %H:%M:%S')))

vehicle_stats = cursor.fetchall()

print(f'\n📊 今日到货统计')
print(f'总车次: {total_vehicles} 辆')
print(f'总件数: {total_pieces:,} 件')
print(f'总托盘: {total_pallets} 托盘')
print(f'\n📦 分拣进度')
print(f'已分拣: {total_sorted_pieces:,} 件')
print(f'剩余未分拣: {(total_pieces - total_sorted_pieces):,} 件')
if total_pieces > 0:
    progress = (total_sorted_pieces / total_pieces) * 100
    print(f'完成度: {progress:.1f}%')

print(f'\n🚛 按车型统计:')
for vtype, count, pieces in vehicle_stats:
    pv = int(round(float(pieces))) if pieces is not None else 0
    print(f'  {vtype}: {count}辆, {pv:,}件')

conn.close()
