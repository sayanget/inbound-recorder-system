import sqlite3
from datetime import datetime, timedelta
import pytz
import os
import sys
import json

print("=== 开始完整调试测试 ===")

# 模拟API中的逻辑
def get_db_path():
    """获取正确的数据库路径"""
    if getattr(sys, 'frozen', False):
        # 打包后的exe环境
        return os.path.join(os.path.dirname(sys.executable), 'inbound.db')
    else:
        # 开发环境
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'inbound.db')

DB_PATH = get_db_path()
print(f"1. 数据库路径: {DB_PATH}")

# 检查数据库文件是否存在
if os.path.exists(DB_PATH):
    print(f"2. 数据库文件存在")
else:
    print(f"2. 数据库文件不存在!")
    sys.exit(1)

# 连接到数据库
try:
    conn = sqlite3.connect(DB_PATH)
    print(f"3. 数据库连接成功")
except Exception as e:
    print(f"3. 数据库连接失败: {e}")
    sys.exit(1)

# 获取洛杉矶当前日期
la_tz = pytz.timezone('America/Los_Angeles')
current_la_time = datetime.now(la_tz)
la_today = current_la_time.date()
print(f"4. 当前洛杉矶时间: {current_la_time}")
print(f"5. 今天日期: {la_today}")

# 计算次日日期
next_date = la_today + timedelta(days=1)
print(f"6. 明天日期: {next_date}")

# 构建日期范围查询条件（使用自然日而不是业务日）
# 当天00:00:00的时间（洛杉矶时间）
today_start_la = la_tz.localize(datetime.combine(la_today, datetime.min.time()))
# 次日00:00:00的时间（洛杉矶时间，用于上限）
next_day_start_la = la_tz.localize(datetime.combine(next_date, datetime.min.time()))

print(f"7. 查询时间范围:")
print(f"   开始时间: {today_start_la}")
print(f"   结束时间: {next_day_start_la}")

# 时间字符串格式
start_time_str = today_start_la.strftime('%Y-%m-%d %H:%M:%S')
end_time_str = next_day_start_la.strftime('%Y-%m-%d %H:%M:%S')
print(f"8. 时间字符串格式:")
print(f"   开始时间字符串: {start_time_str}")
print(f"   结束时间字符串: {end_time_str}")

# 执行查询
print(f"9. 执行查询...")
query = """
    SELECT id, dock_no, vehicle_type, vehicle_no, unit, load_amount,
           pieces, time_slot, shift_type, remark, created_at
    FROM inbound_records 
    WHERE 
        created_at >= ? AND created_at < ?
    ORDER BY created_at DESC
"""

print(f"   查询语句: {query}")
print(f"   查询参数: ({start_time_str}, {end_time_str})")

try:
    cur = conn.execute(query, (start_time_str, end_time_str))
    raw_rows = cur.fetchall()
    print(f"10. 数据库查询成功，返回记录数: {len(raw_rows)}")
    
    if raw_rows:
        print("    原始记录详情:")
        for i, row in enumerate(raw_rows):
            print(f"      {i+1}. ID: {row[0]}, 时间: {row[10]}, 码头: {row[1]}, 车辆: {row[2]}")
    
    # 处理记录
    rows = [{
        "id": r[0], "dock_no": r[1], "vehicle_type": r[2], "vehicle_no": r[3],
        "unit": r[4], "load_amount": r[5], "pieces": r[6],
        "time_slot": r[7], "shift_type": r[8], "remark": r[9],
        "created_at": r[10]  # 数据库中存储的已经是洛杉矶时间，直接返回
    } for r in raw_rows]
    
    print(f"11. 处理后记录数: {len(rows)}")
    
    # 模拟API返回的JSON
    json_result = json.dumps(rows, ensure_ascii=False)
    print(f"12. JSON结果长度: {len(json_result)}")
    print(f"13. JSON结果: {json_result}")
    
except Exception as e:
    print(f"10. 数据库查询失败: {e}")
    import traceback
    traceback.print_exc()

# 关闭连接
conn.close()
print("14. 数据库连接已关闭")
print("=== 调试测试完成 ===")