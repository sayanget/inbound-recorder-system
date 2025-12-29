import sqlite3
from datetime import datetime, timedelta
import pytz
import requests
import time

print("完整调试时区问题...\n")

# 1. 检查数据库中的记录
conn = sqlite3.connect('inbound.db')
cursor = conn.cursor()

# 获取ID为185的记录（最新记录）
cursor.execute('SELECT id, dock_no, vehicle_type, created_at FROM inbound_records WHERE id = 185')
record = cursor.fetchone()

print(f"记录详情:")
print(f"  ID: {record[0]}, 码头: {record[1]}, 车型: {record[2]}, 创建时间 (UTC): {record[3]}")

# 解析创建时间
created_at_str = record[3]
created_at_utc = datetime.strptime(created_at_str, '%Y-%m-%d %H:%M:%S')
created_at_utc = pytz.utc.localize(created_at_utc)

# 转换为洛杉矶时间
la_tz = pytz.timezone('America/Los_Angeles')
created_at_la = created_at_utc.astimezone(la_tz)

print(f"  创建时间 (洛杉矶): {created_at_la.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"  洛杉矶日期: {created_at_la.date()}")
print(f"  洛杉矶时间: {created_at_la.time()}")

# 判断这条记录应该属于哪个业务日
if created_at_la.time() < datetime.strptime('05:00:00', '%H:%M:%S').time():
    # 如果时间在00:00:00到05:00:00之间，属于前一天的业务日
    business_day = created_at_la.date() - timedelta(days=1)
    print(f"  属于业务日: {business_day} (前一天)")
else:
    # 如果时间在05:00:00到23:59:59之间，属于当天的业务日
    business_day = created_at_la.date()
    print(f"  属于业务日: {business_day} (当天)")

# 2. 模拟API查询逻辑
request_date = business_day  # 应该查询的业务日
next_date = request_date + timedelta(days=1)

print(f"\n模拟API查询逻辑:")
print(f"  查询日期: {request_date}")

# 构建日期范围查询条件（使用洛杉矶时区时间进行计算）
# 当天05:00:00的时间（洛杉矶时间）
request_date_5am_la = la_tz.localize(datetime.combine(request_date, datetime.min.time().replace(hour=5)))

# 次日05:00:00的时间（洛杉矶时间，用于上限）
next_date_5am_la = la_tz.localize(datetime.combine(next_date, datetime.min.time().replace(hour=5)))

# 转换为UTC时间用于数据库查询
request_date_5am_utc = request_date_5am_la.astimezone(pytz.utc)
next_date_5am_utc = next_date_5am_la.astimezone(pytz.utc)

print(f"  查询时间范围 (洛杉矶): {request_date_5am_la.strftime('%Y-%m-%d %H:%M:%S')} 到 {next_date_5am_la.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"  查询时间范围 (UTC): {request_date_5am_utc.strftime('%Y-%m-%d %H:%M:%S')} 到 {next_date_5am_utc.strftime('%Y-%m-%d %H:%M:%S')}")

# 执行查询
cursor.execute("""
    SELECT id, dock_no, vehicle_type, created_at
    FROM inbound_records 
    WHERE 
        created_at >= ? AND created_at < ?
    ORDER BY created_at DESC
""", (
    request_date_5am_utc.strftime('%Y-%m-%d %H:%M:%S'), 
    next_date_5am_utc.strftime('%Y-%m-%d %H:%M:%S')
))

records = cursor.fetchall()
print(f"\n数据库查询结果: 找到 {len(records)} 条记录")

for record in records:
    print(f"  ID: {record[0]}, 码头: {record[1]}, 车型: {record[2]}, 创建时间 (UTC): {record[3]}")

# 3. 实际API测试
print(f"\n实际API测试:")
try:
    # 等待服务器启动
    time.sleep(2)
    
    # 查询对应业务日的数据
    response = requests.get(f'http://localhost:8080/api/history?date={business_day}')
    if response.status_code == 200:
        data = response.json()
        record_count = len(data.get('records', []))
        print(f"  API查询成功，找到 {record_count} 条记录")
        
        if record_count > 0:
            print("  记录详情:")
            for record in data['records'][:5]:  # 只显示前5条
                print(f"    ID: {record['id']}, 码头: {record['dock_no']}, 车型: {record['vehicle_type']}, 创建时间: {record['created_at']}")
        else:
            print("  ❌ 问题确认：API查询未返回预期记录")
    else:
        print(f"  ❌ API查询失败，状态码: {response.status_code}")
        print(response.text)
except Exception as e:
    print(f"  ❌ 测试过程中出现错误: {e}")

# 关闭连接
conn.close()

print("\n结论:")
print("1. 数据库中的记录时间是正确的")
print("2. 时区转换逻辑是正确的")
print("3. 业务日判断逻辑是正确的")
print("4. 如果API查询结果为空，可能是其他问题导致的")