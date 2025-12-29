from flask import Flask, jsonify
import sqlite3
from datetime import datetime, timedelta
import pytz
import os
import sys

app = Flask(__name__)

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

@app.route('/api/list')
def list_data():
    print(f"[DEBUG] 数据库路径: {DB_PATH}")
    conn=sqlite3.connect(DB_PATH)
    
    # 获取洛杉矶当前日期
    la_tz = pytz.timezone('America/Los_Angeles')
    la_today = datetime.now(la_tz).date()
    
    # 计算次日日期
    next_date = la_today + timedelta(days=1)
    
    # 构建日期范围查询条件（使用自然日而不是业务日）
    # 当天00:00:00的时间（洛杉矶时间）
    today_start_la = la_tz.localize(datetime.combine(la_today, datetime.min.time()))
    
    # 次日00:00:00的时间（洛杉矶时间，用于上限）
    next_day_start_la = la_tz.localize(datetime.combine(next_date, datetime.min.time()))
    
    print(f"[DEBUG] 查询时间范围: {today_start_la.strftime('%Y-%m-%d %H:%M:%S')} 到 {next_day_start_la.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 查询属于当前自然日的记录（查询当天00:00之后到次日00:00之前的所有记录）
    cur=conn.execute("""
        SELECT id, dock_no, vehicle_type, vehicle_no, unit, load_amount,
               pieces, time_slot, shift_type, remark, created_at
        FROM inbound_records 
        WHERE 
            created_at >= ? AND created_at < ?
        ORDER BY created_at DESC""", (
            today_start_la.strftime('%Y-%m-%d %H:%M:%S'), 
            next_day_start_la.strftime('%Y-%m-%d %H:%M:%S')
        ))
    
    raw_rows = cur.fetchall()
    print(f"[DEBUG] 数据库查询返回记录数: {len(raw_rows)}")
    
    rows=[{
        "id":r[0], "dock_no":r[1], "vehicle_type":r[2], "vehicle_no":r[3],
        "unit":r[4], "load_amount":r[5], "pieces":r[6],
        "time_slot":r[7], "shift_type":r[8], "remark":r[9],
        "created_at":r[10]  # 数据库中存储的已经是洛杉矶时间，直接返回
    } for r in raw_rows]
    
    print(f"[DEBUG] 处理后返回记录数: {len(rows)}")
    conn.close()
    return jsonify(rows)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)