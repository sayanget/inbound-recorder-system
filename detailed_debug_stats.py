#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
详细调试统计数据API
"""

import sqlite3
import os
from datetime import datetime, timedelta

def detailed_debug_stats():
    """详细调试统计数据"""
    try:
        # 连接到数据库
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'inbound.db')
        conn = sqlite3.connect(db_path)
        
        # 获取系统当前日期
        request_date = datetime.now().date()
        print(f"请求日期: {request_date}")
        
        # 计算次日日期
        next_date = request_date + timedelta(days=1)
        print(f"次日日期: {next_date}")
        
        # 构建日期范围查询条件（使用早上5点到第二天早上5点的时间段）
        # 当天05:00:00的时间（系统时间）
        today_start = datetime.combine(request_date, datetime.min.time().replace(hour=5))    
        # 次日05:00:00的时间（系统时间，用于上限）
        next_day_start = datetime.combine(next_date, datetime.min.time().replace(hour=5))
        
        print(f"查询时间范围: {today_start} 到 {next_day_start}")
        
        # 查询属于指定时间段的记录
        records_query = """
            SELECT id, created_at, vehicle_type, time_slot FROM inbound_records 
            WHERE 
                created_at >= ? AND created_at < ?
        """
        records_cur = conn.execute(records_query, (
            today_start.strftime('%Y-%m-%d %H:%M:%S'), 
            next_day_start.strftime('%Y-%m-%d %H:%M:%S')
        ))
        records = records_cur.fetchall()
        print(f"找到 {len(records)} 条记录")
        
        # 显示找到的记录
        for record in records:
            print(f"  ID: {record[0]}, 时间: {record[1]}, 类型: {record[2]}, 时间段: {record[3]}")
        
        # 总车次和总货物量
        total_query = """
            SELECT COUNT(*) as total_vehicles, SUM(pieces) as total_pieces 
            FROM inbound_records 
            WHERE 
                created_at >= ? AND created_at < ? AND NOT (vehicle_type = '53英尺' AND (vehicle_no LIKE '%G%' OR vehicle_no = 'G'))
        """
        total_cur = conn.execute(total_query, (
            today_start.strftime('%Y-%m-%d %H:%M:%S'), 
            next_day_start.strftime('%Y-%m-%d %H:%M:%S')
        ))
        total_result = total_cur.fetchone()
        total_vehicles = total_result[0] if total_result[0] else 0
        total_pieces = int(total_result[1]) if total_result[1] else 0
        print(f"总车次: {total_vehicles}, 总货物量: {total_pieces}")
        
        # 托盘总数
        pallet_query = """
            SELECT SUM(load_amount) as total_pallets
            FROM inbound_records 
            WHERE 
                created_at >= ? AND created_at < ? AND (vehicle_type = '26英尺' OR vehicle_type = '53英尺') AND NOT (vehicle_type = '53英尺' AND (vehicle_no LIKE '%G%' OR vehicle_no = 'G'))
        """
        pallet_cur = conn.execute(pallet_query, (
            today_start.strftime('%Y-%m-%d %H:%M:%S'), 
            next_day_start.strftime('%Y-%m-%d %H:%M:%S')
        ))
        pallet_result = pallet_cur.fetchone()
        total_pallets = int(pallet_result[0]) if pallet_result[0] else 0
        print(f"托盘总数: {total_pallets}")
        
        # 各车型统计
        vehicle_stats_query = """
            SELECT vehicle_type, COUNT(*) as count, SUM(pieces) as total_pieces 
            FROM inbound_records 
            WHERE 
                created_at >= ? AND created_at < ? AND NOT (vehicle_type = '53英尺' AND (vehicle_no LIKE '%G%' OR vehicle_no = 'G'))
            GROUP BY vehicle_type
        """
        vehicle_stats_cur = conn.execute(vehicle_stats_query, (
            today_start.strftime('%Y-%m-%d %H:%M:%S'), 
            next_day_start.strftime('%Y-%m-%d %H:%M:%S')
        ))
        vehicle_stats = [{
            "vehicle_type": r[0],
            "count": r[1],
            "total_pieces": int(r[2]) if r[2] else 0
        } for r in vehicle_stats_cur.fetchall()]
        print(f"各车型统计: {vehicle_stats}")
        
        conn.close()
        
        # 模拟API返回的结果
        result = {
            "total_vehicles": total_vehicles,
            "total_pieces": total_pieces,
            "total_pallets": total_pallets,
            "vehicle_stats": vehicle_stats,
            "vehicles_19_to_20": 0,
            "vehicles_19_to_20_by_type": {},
            "vehicles_20_to_21": 0,
            "vehicles_20_to_21_by_type": {},
            "vehicles_after_24": 0
        }
        
        print("\n模拟API返回结果:")
        import json
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"调试过程中出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    detailed_debug_stats()