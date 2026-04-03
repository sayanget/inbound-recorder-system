#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立测试API逻辑
"""

import sqlite3
import os
import sys
from datetime import datetime
import json

def get_db_path():
    # 首先检查环境变量
    db_path_env = os.environ.get('DATABASE_PATH')
    if db_path_env:
        return db_path_env
    
    # 如果是打包后的exe环境，数据库在同级目录下
    if getattr(sys, 'frozen', False):
        # 打包后的exe环境
        return os.path.join(os.path.dirname(sys.executable), 'inbound.db')
    else:
        # 开发环境
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'inbound.db')

def test_api_logic():
    """测试API逻辑"""
    print("独立测试API逻辑")
    print("=" * 50)
    
    db_path = get_db_path()
    print(f"数据库路径: {db_path}")
    
    # 检查文件是否存在
    if not os.path.exists(db_path):
        print("数据库文件不存在")
        return
    
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        print("数据库连接成功")
        
        # 检查表是否存在
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='inbound_records';")
        table_exists = cursor.fetchone()
        
        if not table_exists:
            print("inbound_records 表不存在")
            conn.close()
            return
        
        print("inbound_records 表存在")
        
        # 查询所有记录数
        cursor = conn.execute("SELECT COUNT(*) FROM inbound_records;")
        count = cursor.fetchone()[0]
        print(f"总记录数: {count}")
        
        # 执行API中的查询逻辑
        print("\n执行API查询逻辑:")
        cur = conn.execute("""
            SELECT id, dock_no, vehicle_type, vehicle_no, unit, load_amount,
                   pieces, time_slot, shift_type, remark, created_at
            FROM inbound_records 
            ORDER BY created_at DESC""")
        
        raw_rows = cur.fetchall()
        print(f"查询返回记录数: {len(raw_rows)}")
        
        # 处理记录
        rows = [{
            "id": r[0], "dock_no": r[1], "vehicle_type": r[2], "vehicle_no": r[3],
            "unit": r[4], "load_amount": r[5], "pieces": r[6],
            "time_slot": r[7], "shift_type": r[8], "remark": r[9],
            "created_at": r[10]  # 数据库中存储的是系统时间，直接返回
        } for r in raw_rows]
        
        print(f"处理后记录数: {len(rows)}")
        
        # 显示前5条记录
        if rows:
            print("\n前5条记录:")
            for i, row in enumerate(rows[:5]):
                print(f"  {i+1}. ID: {row['id']}, 车型: {row['vehicle_type']}, 创建时间: {row['created_at']}")
        
        # 保存到文件
        with open('api_test_result.json', 'w', encoding='utf-8') as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存到 api_test_result.json")
        
        conn.close()
        
    except Exception as e:
        print(f"测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_api_logic()