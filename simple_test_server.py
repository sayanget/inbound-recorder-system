#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单的测试服务器
"""

import sqlite3
import os
import sys
from datetime import datetime, timedelta
import pytz
from flask import Flask, jsonify

app = Flask(__name__)

# 数据库路径
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'inbound.db')

@app.route('/api/list')
def list_data():
    print("[DEBUG] /api/list 路由被调用")
    print("[DEBUG] 函数开始执行")
    conn = sqlite3.connect(DB_PATH)
    print(f"[DEBUG] 数据库连接成功: {DB_PATH}")
    
    # 获取洛杉矶当前日期
    la_tz = pytz.timezone('America/Los_Angeles')
    la_now = datetime.now(la_tz)
    print(f"[DEBUG] 洛杉矶当前时间: {la_now}")
    
    # 计算业务日
    if la_now.hour < 5:
        # 如果当前洛杉矶时间在05:00之前，使用昨天的日期作为业务日
        business_day = la_now.date() - timedelta(days=1)
        print(f"[DEBUG] 业务日在05:00之前，使用昨天日期: {business_day}")
    else:
        # 否则使用今天的日期作为业务日
        business_day = la_now.date()
        print(f"[DEBUG] 业务日在05:00之后，使用今天日期: {business_day}")
    
    # 计算次日日期
    next_date = business_day + timedelta(days=1)
    print(f"[DEBUG] 业务日次日: {next_date}")
    
    # 构建日期范围查询条件（使用洛杉矶时区时间进行计算）
    # 当天05:00:00的时间（洛杉矶时间）
    business_day_5am_la = la_tz.localize(datetime.combine(business_day, datetime.min.time().replace(hour=5)))
    
    # 次日05:00:00的时间（洛杉矶时间，用于上限）
    next_day_5am_la = la_tz.localize(datetime.combine(next_date, datetime.min.time().replace(hour=5)))
    
    # 转换为系统本地时间用于数据库查询
    # 注意：数据库中存储的是系统本地时间，不是UTC时间
    business_day_5am_local = business_day_5am_la.astimezone()
    next_day_5am_local = next_day_5am_la.astimezone()
    
    print(f"[DEBUG] 查询时间范围 (系统时间): {business_day_5am_local} 到 {next_day_5am_local}")
    
    # 查询属于指定时间段的记录（查询当天05:00之后到次日05:00之前的所有记录）
    cur = conn.execute("""
        SELECT id, dock_no, vehicle_type, vehicle_no, unit, load_amount,
               pieces, time_slot, shift_type, remark, created_at
        FROM inbound_records 
        WHERE 
            created_at >= ? AND created_at < ?
        ORDER BY created_at DESC""", (
            business_day_5am_local.strftime('%Y-%m-%d %H:%M:%S'), 
            next_day_5am_local.strftime('%Y-%m-%d %H:%M:%S')
        ))
    
    raw_rows = cur.fetchall()
    print(f"[DEBUG] 数据库查询返回记录数: {len(raw_rows)}")
    
    rows = [{
        "id": r[0], "dock_no": r[1], "vehicle_type": r[2], "vehicle_no": r[3],
        "unit": r[4], "load_amount": r[5], "pieces": r[6],
        "time_slot": r[7], "shift_type": r[8], "remark": r[9],
        "created_at": r[10]  # 数据库中存储的是系统时间，直接返回
    } for r in raw_rows]
    
    print(f"[DEBUG] 处理后返回记录数: {len(rows)}")
    conn.close()
    print(f"[DEBUG] 返回JSON数据记录数: {len(rows)}")
    response = jsonify(rows)
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response

if __name__ == '__main__':
    print("启动测试服务器...")
    app.run(host='0.0.0.0', port=8081, debug=True)