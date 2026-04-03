#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3
import os
from datetime import datetime, timedelta
import pytz
import json
import sys

INBOUND_PIECES_ACTUAL_FACTOR = float(os.environ.get("INBOUND_PIECES_ACTUAL_FACTOR", "0.76"))

# 设置输出编码
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

conn = sqlite3.connect('inbound.db')
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
today_start_local = today_start.astimezone()
next_day_start_local = next_day_start.astimezone()

print("业务日期:", business_date)
print("当前时间:", now_la.strftime('%Y-%m-%d %H:%M:%S'))
print()

# 查询总件数和总托盘数
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

# 获取分拣配置
cursor.execute("SELECT config_json FROM sorting_schedule_config ORDER BY updated_at DESC LIMIT 1")
config_row = cursor.fetchone()

defaults = {
    "manual": {"capacity": 3000, "schedule": [5, 5, 5, 4, 4, 4, 1]},
    "machine": {"capacity": 4500, "schedule": [4, 4, 4, 4, 4, 2, 2]},
    "night": {"capacity": 4500, "schedule": [0, 0, 0, 0, 0, 0, 0]}
}

config = json.loads(config_row[0]) if config_row else defaults

day_of_week = business_date.weekday()
manual_schedule = config.get('manual', {}).get('schedule', defaults['manual']['schedule'])
machine_schedule = config.get('machine', {}).get('schedule', defaults['machine']['schedule'])
night_schedule = config.get('night', {}).get('schedule', [0]*7)

manual_lanes = manual_schedule[day_of_week]
machine_lanes = machine_schedule[day_of_week]
night_lanes = night_schedule[day_of_week] if day_of_week < len(night_schedule) else 0

manual_cap = config.get('manual', {}).get('capacity', 3000)
machine_cap = config.get('machine', {}).get('capacity', 4500)
night_cap = config.get('night', {}).get('capacity', 4500)

# 计算理论已分拣量
PIECES_PER_PALLET = 344
sorting_start_time = datetime.combine(business_date, datetime.min.time().replace(hour=17, minute=0, second=0))
sorting_start_time_aware = la_tz.localize(sorting_start_time)
now = datetime.now(la_tz)

theoretical_sorted_pieces = 0
theoretical_sorted_pallets = 0

if now >= sorting_start_time_aware:
    phase1_end = datetime.combine(business_date, datetime.min.time().replace(hour=23, minute=0, second=0))
    phase1_end_aware = la_tz.localize(phase1_end)
    
    phase1_hourly_capacity = (manual_lanes * manual_cap) + (machine_lanes * machine_cap)
    phase2_hourly_capacity = night_lanes * night_cap
    
    if now < phase1_end_aware:
        phase1_elapsed = (now - sorting_start_time_aware).total_seconds() / 3600
        theoretical_sorted_pieces = phase1_elapsed * phase1_hourly_capacity
        theoretical_sorted_pallets = theoretical_sorted_pieces / PIECES_PER_PALLET
    else:
        phase1_duration = 6
        theoretical_sorted_pieces = phase1_duration * phase1_hourly_capacity
        theoretical_sorted_pallets = theoretical_sorted_pieces / PIECES_PER_PALLET
        
        phase2_elapsed = (now - phase1_end_aware).total_seconds() / 3600
        theoretical_sorted_pieces += phase2_elapsed * phase2_hourly_capacity
        theoretical_sorted_pallets = theoretical_sorted_pieces / PIECES_PER_PALLET

# 计算实际已分拣托盘数
recorded_sorted_pallets = total_sorted_pieces / PIECES_PER_PALLET if total_sorted_pieces > 0 else 0
sorted_pallets = max(theoretical_sorted_pallets, recorded_sorted_pallets)

# 计算剩余托盘数
remaining_pallets = max(0, total_pallets - sorted_pallets)

# 计算剩余件数
remaining_pieces = max(0, total_pieces - sorted_pallets * PIECES_PER_PALLET)

# 计算预计完成时间
estimated_completion_time = None
remaining_duration_minutes = None

if remaining_pieces > 0:
    current_time = datetime.now()
    pieces_left = remaining_pieces
    
    phase1_cap = (manual_lanes * manual_cap) + (machine_lanes * machine_cap)
    phase2_cap = night_lanes * night_cap
    
    max_loops = 7 * 3
    loops = 0
    
    while pieces_left > 0 and loops < max_loops:
        loops += 1
        t = current_time.time()
        
        t17 = datetime.min.time().replace(hour=17)
        t23 = datetime.min.time().replace(hour=23)
        t05 = datetime.min.time().replace(hour=5)
        
        capacity = 0
        next_time = None
        
        if t >= t17 and t < t23:
            capacity = phase1_cap
            next_time = datetime.combine(current_time.date(), t23)
        elif t >= t23:
            capacity = phase2_cap
            next_time = datetime.combine(current_time.date() + timedelta(days=1), t05)
        elif t < t05:
            capacity = phase2_cap
            next_time = datetime.combine(current_time.date(), t05)
        else:
            capacity = 0
            next_time = datetime.combine(current_time.date(), t17)
        
        if next_time <= current_time:
            next_time += timedelta(days=1)
        
        available_hours = (next_time - current_time).total_seconds() / 3600.0
        
        if capacity > 0:
            potential_production = available_hours * capacity
            
            if pieces_left <= potential_production:
                hours_needed = pieces_left / capacity
                estimated_completion_time = current_time + timedelta(hours=hours_needed)
                break
            else:
                pieces_left -= potential_production
                current_time = next_time
        else:
            current_time = next_time
    
    if estimated_completion_time:
        remaining_duration = (estimated_completion_time - datetime.now()).total_seconds() / 60
        remaining_duration_minutes = max(0, int(remaining_duration))

# 输出结果
print("=" * 60)
print("查询结果")
print("=" * 60)
print(f"总车次: {total_vehicles} 辆")
print(f"总件数: {total_pieces:,} 件")
print(f"总托盘: {total_pallets} 托盘")

weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
print(f"\n分拣配置 ({weekdays[day_of_week]}):")
print(f"  人工: {manual_lanes}道 x {manual_cap}件/小时 = {manual_lanes * manual_cap:,}件/小时")
print(f"  机器: {machine_lanes}道 x {machine_cap}件/小时 = {machine_lanes * machine_cap:,}件/小时")
print(f"  夜班: {night_lanes}道 x {night_cap}件/小时 = {night_lanes * night_cap:,}件/小时")

print("\n" + "=" * 60)
print("最终结果")
print("=" * 60)
print(f"已分拣件数: {total_sorted_pieces:,} 件")
print(f"托盘余量: {round(remaining_pallets)} 托盘")

if estimated_completion_time:
    print(f"预计完成时间: {estimated_completion_time.strftime('%Y-%m-%d %H:%M')}")
    hours = remaining_duration_minutes // 60
    minutes = remaining_duration_minutes % 60
    print(f"分拣预计时长: {hours}小时{minutes}分钟")
else:
    print(f"预计完成时间: 已完成")
    print(f"分拣预计时长: 0小时0分钟")

print("=" * 60)

conn.close()
