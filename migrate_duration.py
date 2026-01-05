import sqlite3
import os
import sys
from datetime import datetime

# 设置控制台输出编码为UTF-8
sys.stdout.reconfigure(encoding='utf-8')

def get_db_path():
    """获取数据库路径"""
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'inbound.db')
    else:
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'inbound.db')

def update_duration():
    print('开始更新历史记录时长...')
    print('注意: 将排除 Car 和 Van 车型')
    print()

    db_path = get_db_path()
    if not os.path.exists(db_path):
        print(f"找不到数据库文件: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. 重置所有时长
        cursor.execute('UPDATE inbound_records SET duration = NULL')
        print('✓ 已重置所有时长为 NULL')

        # 2. 获取所有道口
        cursor.execute('SELECT DISTINCT dock_no FROM inbound_records WHERE dock_no IS NOT NULL ORDER BY dock_no')
        dock_numbers = [row[0] for row in cursor.fetchall()]
        print(f'✓ 找到 {len(dock_numbers)} 个道口')
        print()

        # 3. 为每个道口计算时长(排除Car和Van)
        total_updated = 0
        for dock_no in dock_numbers:
            # 只查询非Car/Van的记录
            cursor.execute('''
                SELECT id, created_at, vehicle_type 
                FROM inbound_records 
                WHERE dock_no = ? AND vehicle_type NOT IN ("Car", "Van")
                ORDER BY created_at ASC
            ''', (dock_no,))
            
            records = cursor.fetchall()
            
            if len(records) == 0:
                continue
            
            # 计算每条记录的时长(除了最后一条)
            updated_count_for_dock = 0
            for i in range(len(records) - 1):
                current_id = records[i][0]
                try:
                    current_time = datetime.strptime(records[i][1], '%Y-%m-%d %H:%M:%S')
                    next_time = datetime.strptime(records[i + 1][1], '%Y-%m-%d %H:%M:%S')
                    
                    duration = int((next_time - current_time).total_seconds() / 60)
                    if duration < 0:
                        duration = 0
                    
                    cursor.execute('UPDATE inbound_records SET duration = ? WHERE id = ?', (duration, current_id))
                    updated_count_for_dock += 1
                    total_updated += 1
                except Exception as e:
                    print(f"  Warning: 处理记录ID {current_id} 时间格式错误: {e}")
            
            if updated_count_for_dock > 0:
                print(f'  道口 {dock_no}: 更新了 {updated_count_for_dock} 条大车记录')

        conn.commit()

        # 4. 统计
        cursor.execute('SELECT COUNT(*) FROM inbound_records WHERE duration IS NOT NULL')
        with_duration = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM inbound_records WHERE duration IS NULL')
        without_duration = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM inbound_records WHERE vehicle_type IN ("Car", "Van")')
        car_van_count = cursor.fetchone()[0]

        print()
        print('=' * 50)
        print(f'✓ 完成! 共更新 {total_updated} 条记录的时长')
        print(f'  - 有时长(已完成的大车): {with_duration} 条')
        print(f'  - 无时长(占用中/小车): {without_duration} 条')
        print(f'    (其中 Car/Van: {car_van_count} 条)')
        print('=' * 50)

    except Exception as e:
        print(f"❌ 发生错误: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    update_duration()
