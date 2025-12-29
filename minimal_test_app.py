#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最小化测试应用
"""

from flask import Flask, jsonify
import sqlite3
import os
import sys

app = Flask(__name__)

# 获取数据库路径
def get_db_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'inbound.db')

@app.route('/api/list')
def list_data():
    print("[DEBUG] /api/list 路由被调用")
    
    db_path = get_db_path()
    print(f"[DEBUG] 数据库路径: {db_path}")
    
    # 检查数据库文件是否存在
    if not os.path.exists(db_path):
        print("[DEBUG] 数据库文件不存在")
        return jsonify([])
    
    try:
        conn = sqlite3.connect(db_path)
        print("[DEBUG] 数据库连接成功")
        
        # 查询所有记录
        cur = conn.execute("""
            SELECT id, dock_no, vehicle_type, vehicle_no, unit, load_amount,
                   pieces, time_slot, shift_type, remark, created_at
            FROM inbound_records 
            ORDER BY created_at DESC""")
        
        raw_rows = cur.fetchall()
        print(f"[DEBUG] 数据库查询返回记录数: {len(raw_rows)}")
        
        rows = [{
            "id": r[0], "dock_no": r[1], "vehicle_type": r[2], "vehicle_no": r[3],
            "unit": r[4], "load_amount": r[5], "pieces": r[6],
            "time_slot": r[7], "shift_type": r[8], "remark": r[9],
            "created_at": r[10]
        } for r in raw_rows]
        
        print(f"[DEBUG] 处理后返回记录数: {len(rows)}")
        conn.close()
        
        # 返回UTF-8编码的JSON数据
        response = jsonify(rows)
        response.headers['Content-Type'] = 'application/json; charset=utf-8'
        return response
        
    except Exception as e:
        print(f"[DEBUG] 查询时出错: {e}")
        if 'conn' in locals():
            conn.close()
        return jsonify([])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8085, debug=True)