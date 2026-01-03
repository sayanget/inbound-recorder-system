#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库迁移脚本: 为 inbound_records 表添加 duration 字段
用途: 记录每次道口占用的时间长度(单位:分钟)
"""

import sqlite3
import os
import sys

def get_db_path():
    """获取数据库路径"""
    if getattr(sys, 'frozen', False):
        # 打包后的exe环境
        return os.path.join(os.path.dirname(sys.executable), 'inbound.db')
    else:
        # 开发环境
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'inbound.db')

def add_duration_field():
    """为 inbound_records 表添加 duration 字段"""
    db_path = get_db_path()
    
    if not os.path.exists(db_path):
        print(f"错误: 数据库文件不存在: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查字段是否已存在
        cursor.execute("PRAGMA table_info(inbound_records)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'duration' in columns:
            print("duration 字段已存在,无需添加")
            conn.close()
            return True
        
        # 添加 duration 字段
        print("正在添加 duration 字段...")
        cursor.execute("""
            ALTER TABLE inbound_records 
            ADD COLUMN duration INTEGER
        """)
        
        conn.commit()
        print("✓ 成功添加 duration 字段")
        
        # 验证字段是否添加成功
        cursor.execute("PRAGMA table_info(inbound_records)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'duration' in columns:
            print("✓ 验证成功: duration 字段已添加到数据库")
            print(f"\n当前 inbound_records 表的所有字段:")
            for col in columns:
                print(f"  - {col}")
        else:
            print("✗ 验证失败: duration 字段未能添加")
            return False
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"错误: 添加字段时发生异常: {e}")
        if 'conn' in locals():
            conn.close()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("数据库迁移: 添加 duration 字段")
    print("=" * 60)
    print()
    
    success = add_duration_field()
    
    print()
    if success:
        print("✓ 数据库迁移成功完成")
    else:
        print("✗ 数据库迁移失败")
        sys.exit(1)
