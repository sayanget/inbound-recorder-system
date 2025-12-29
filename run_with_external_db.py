#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运行InboundRecorder并指定外部数据库文件
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def run_with_external_db(db_path=None, exe_path=None):
    """使用指定的外部数据库文件运行InboundRecorder"""
    
    # 获取项目根目录
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    # 如果没有指定exe路径，使用默认路径
    if exe_path is None:
        exe_path = os.path.join(project_root, "dist", "InboundRecorder.exe")
    
    # 检查exe文件是否存在
    if not os.path.exists(exe_path):
        print(f"错误: 找不到可执行文件 {exe_path}")
        return False
    
    # 如果没有指定数据库路径，使用项目目录下的数据库
    if db_path is None:
        db_path = os.path.join(project_root, "inbound.db")
    
    # 检查数据库文件是否存在
    if not os.path.exists(db_path):
        print(f"警告: 数据库文件 {db_path} 不存在，将在首次运行时创建")
    
    # 获取exe文件所在目录
    exe_dir = os.path.dirname(exe_path)
    
    # 检查exe目录下是否已有数据库文件
    local_db = os.path.join(exe_dir, "inbound.db")
    if os.path.exists(local_db):
        print(f"注意: EXE目录下已存在数据库文件 {local_db}")
        print("如果您想使用外部数据库，请确保该文件不会被覆盖")
    
    # 设置环境变量指定数据库路径
    env = os.environ.copy()
    env['DATABASE_PATH'] = db_path
    
    print(f"正在使用数据库文件: {db_path}")
    print(f"正在运行可执行文件: {exe_path}")
    print("=" * 50)
    
    try:
        # 运行exe文件并传递环境变量
        process = subprocess.Popen([exe_path], env=env)
        print("应用已启动，请在浏览器中访问:")
        print("本地访问: http://localhost:8080")
        print("网络访问: http://192.168.2.198:8080")
        print("按 Ctrl+C 可停止应用")
        print("=" * 50)
        
        # 等待进程结束
        process.wait()
        return True
        
    except Exception as e:
        print(f"运行过程中出现错误: {e}")
        return False

def copy_db_to_exe_dir(source_db=None, exe_dir=None):
    """将指定的数据库文件复制到exe目录"""
    
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    # 如果没有指定源数据库，使用项目目录下的数据库
    if source_db is None:
        source_db = os.path.join(project_root, "inbound.db")
    
    # 如果没有指定exe目录，使用默认目录
    if exe_dir is None:
        exe_dir = os.path.join(project_root, "dist")
    
    # 检查源数据库是否存在
    if not os.path.exists(source_db):
        print(f"错误: 源数据库文件 {source_db} 不存在")
        return False
    
    # 目标数据库路径
    target_db = os.path.join(exe_dir, "inbound.db")
    
    try:
        # 复制数据库文件
        import shutil
        shutil.copy2(source_db, target_db)
        print(f"已将数据库文件从 {source_db} 复制到 {target_db}")
        return True
    except Exception as e:
        print(f"复制数据库文件时出现错误: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='运行InboundRecorder并指定外部数据库文件')
    parser.add_argument('--db', '-d', help='指定数据库文件路径')
    parser.add_argument('--exe', '-e', help='指定可执行文件路径')
    parser.add_argument('--copy-db', action='store_true', help='将项目数据库复制到exe目录')
    parser.add_argument('--source-db', help='源数据库文件路径（用于复制）')
    parser.add_argument('--target-dir', help='目标目录路径（用于复制）')
    
    args = parser.parse_args()
    
    print("InboundRecorder 外部数据库运行工具")
    print("=" * 50)
    
    # 如果指定了复制数据库选项
    if args.copy_db:
        success = copy_db_to_exe_dir(args.source_db, args.target_dir)
        if success:
            print("数据库复制完成")
        else:
            print("数据库复制失败")
        return
    
    # 运行应用
    success = run_with_external_db(args.db, args.exe)
    if success:
        print("应用运行完成")
    else:
        print("应用运行失败")

if __name__ == "__main__":
    main()