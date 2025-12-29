import sqlite3
from datetime import datetime, timedelta
import json
import sys
import os

# 获取数据库路径
def get_db_path():
    # 如果是打包后的exe环境，数据库在同级目录下
    if getattr(sys, 'frozen', False):
        # 打包后的exe环境
        return os.path.join(os.path.dirname(sys.executable), 'inbound.db')
    else:
        # 开发环境
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'inbound.db')

DB_PATH = get_db_path()
print(f"数据库路径: {DB_PATH}")

def list_data():
    print("[DEBUG] /api/list 路由被调用")
    conn=sqlite3.connect(DB_PATH)
    print(f"[DEBUG] 数据库连接成功: {DB_PATH}")
    
    # 获取系统当前日期
    today = datetime.now().date()
    print(f"[DEBUG] 当前系统日期: {today}")
    
    # 计算次日日期
    next_date = today + timedelta(days=1)
    print(f"[DEBUG] 次日日期: {next_date}")
    
    # 构建日期范围查询条件（使用自然日）
    # 当天00:00:00的时间（系统时间）
    today_start = datetime.combine(today, datetime.min.time())
    
    # 次日00:00:00的时间（系统时间，用于上限）
    next_day_start = datetime.combine(next_date, datetime.min.time())
    
    print(f"[DEBUG] 查询时间范围: {today_start} 到 {next_day_start}")
    
    # 查询属于当前自然日的记录（查询当天00:00之后到次日00:00之前的所有记录）
    cur=conn.execute("""
        SELECT id, dock_no, vehicle_type, vehicle_no, unit, load_amount,
               pieces, time_slot, shift_type, remark, created_at
        FROM inbound_records 
        WHERE 
            created_at >= ? AND created_at < ?
        ORDER BY created_at DESC""", (
            today_start.strftime('%Y-%m-%d %H:%M:%S'), 
            next_day_start.strftime('%Y-%m-%d %H:%M:%S')
        ))
    
    raw_rows = cur.fetchall()
    print(f"[DEBUG] 数据库查询返回记录数: {len(raw_rows)}")
    
    rows=[{
        "id":r[0], "dock_no":r[1], "vehicle_type":r[2], "vehicle_no":r[3],
        "unit":r[4], "load_amount":r[5], "pieces":r[6],
        "time_slot":r[7], "shift_type":r[8], "remark":r[9],
        "created_at":r[10]  # 数据库中存储的是系统时间，直接返回
    } for r in raw_rows]
    
    print(f"[DEBUG] 处理后返回记录数: {len(rows)}")
    conn.close()
    # print(f"[DEBUG] 返回JSON数据: {jsonify(rows)}")
    return rows

# 直接调用函数
print("直接调用list_data函数:")
result = list_data()
print("函数返回记录数:", len(result))
print("前3条记录:")
for i, record in enumerate(result[:3]):
    print(f"  {i+1}. ID: {record['id']}, 时间: {record['created_at']}")