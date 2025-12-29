#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
详细分析业务日归属情况
"""

import sqlite3
import pytz
from datetime import datetime, timedelta
import json

# 数据库路径
DB_PATH = 'inbound.db'

# 定义洛杉矶时区
LA_TZ = pytz.timezone('America/Los_Angeles')

def analyze_business_day_assignment():
    """
    详细分析每条记录的业务日归属情况
    """
    conn = sqlite3.connect(DB_PATH)
    
    try:
        # 获取所有记录
        cur = conn.execute("""
            SELECT id, created_at, dock_no, vehicle_type, pieces 
            FROM inbound_records 
            ORDER BY created_at
        """)
        records = cur.fetchall()
        
        print(f"总共找到 {len(records)} 条记录")
        print("\n详细业务日归属分析:")
        print("=" * 100)
        print(f"{'ID':<5} {'创建时间(UTC)':<20} {'洛杉矶时间':<20} {'业务日':<12} {'归属说明':<30}")
        print("-" * 100)
        
        business_day_stats = {}
        
        for record in records:
            record_id, created_at, dock_no, vehicle_type, pieces = record
            
            try:
                # 解析UTC时间字符串
                utc_time = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
                utc_time = pytz.utc.localize(utc_time)
                # 转换为洛杉矶时间
                la_time = utc_time.astimezone(LA_TZ)
                la_time_str = la_time.strftime('%Y-%m-%d %H:%M:%S')
                
                # 确定业务日
                if la_time.hour < 5:
                    business_date = la_time.date() - timedelta(days=1)
                    assignment_reason = f"次日{la_time.hour:02d}时，归属前日"
                else:
                    business_date = la_time.date()
                    assignment_reason = f"当日{la_time.hour:02d}时，归属当日"
                
                business_date_str = business_date.strftime('%Y-%m-%d')
                
                # 统计业务日记录数
                if business_date_str not in business_day_stats:
                    business_day_stats[business_date_str] = 0
                business_day_stats[business_date_str] += 1
                
                print(f"{record_id:<5} {created_at:<20} {la_time_str:<20} {business_date_str:<12} {assignment_reason:<30}")
                
            except Exception as e:
                print(f"{record_id:<5} {created_at:<20} {'解析错误':<20} {'错误':<12} {str(e):<30}")
        
        print("\n" + "=" * 100)
        print("业务日统计汇总:")
        print("-" * 50)
        total_reassigned = 0
        for business_date in sorted(business_day_stats.keys()):
            count = business_day_stats[business_date]
            print(f"业务日 {business_date}: {count} 条记录")
            
            # 检查是否有在00:00-05:00之间归属到前一天的记录
            reassigned_count = 0
            for record in records:
                record_id, created_at, dock_no, vehicle_type, pieces = record
                try:
                    utc_time = datetime.strptime(created_at, '%Y-%m-%d %H:%M:%S')
                    utc_time = pytz.utc.localize(utc_time)
                    la_time = utc_time.astimezone(LA_TZ)
                    if la_time.hour < 5:
                        record_business_date = la_time.date() - timedelta(days=1)
                        if record_business_date.strftime('%Y-%m-%d') == business_date:
                            reassigned_count += 1
                except:
                    pass
            
            if reassigned_count > 0:
                print(f"  其中 {reassigned_count} 条记录是从次日00:00-05:00归属过来的")
                total_reassigned += reassigned_count
        
        print(f"\n总计: {sum(business_day_stats.values())} 条记录")
        print(f"其中 {total_reassigned} 条记录因在次日00:00-05:00录入而被归属到前一天")
        
        # 验证当前API逻辑
        print("\n" + "=" * 100)
        print("验证当前API逻辑:")
        print("-" * 50)
        
        # 获取洛杉矶当前日期
        la_today = datetime.now(LA_TZ).date()
        la_yesterday = la_today - timedelta(days=1)
        
        yesterday_start = la_yesterday.strftime('%Y-%m-%d 00:00:00')
        today_early_end = la_today.strftime('%Y-%m-%d 05:00:00')
        
        # 查询属于当前业务日的记录（使用新逻辑）
        cur = conn.execute("""
            SELECT id, created_at FROM inbound_records 
            WHERE 
                (DATE(created_at) = ?)  -- 今天的记录
                OR 
                (created_at >= ? AND created_at < ?)  -- 昨天00:00到今天05:00的记录
            ORDER BY created_at
            """, (la_today.strftime('%Y-%m-%d'), yesterday_start, today_early_end))
        current_business_day_records = cur.fetchall()
        
        print(f"使用新逻辑，当前业务日 ({la_today}) 应包含 {len(current_business_day_records)} 条记录")
        
        return business_day_stats
        
    except Exception as e:
        print(f"分析记录时出错: {e}")
        return {}
    finally:
        conn.close()

if __name__ == "__main__":
    analyze_business_day_assignment()