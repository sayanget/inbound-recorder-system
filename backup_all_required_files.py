#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
备份项目所有必要关联文件
"""

import os
import shutil
import zipfile
from datetime import datetime
import sys

def get_db_path():
    """获取数据库路径"""
    if getattr(sys, 'frozen', False):
        # 打包后的exe环境
        return os.path.join(os.path.dirname(sys.executable), 'inbound.db')
    else:
        # 开发环境
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'inbound.db')

def backup_required_files():
    """备份所有必要关联文件"""
    # 获取当前时间戳
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"project_backup_required_{timestamp}"
    
    # 创建备份目录
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    print(f"开始备份到目录: {backup_dir}")
    
    # 必要的核心文件列表
    required_files = [
        "single_app.py",
        "inbound.db",
        "requirements.txt",
        "DEPLOYMENT.md",
        "DEPLOYMENT_FULL.md",
        "Dockerfile",
        "docker-compose.yml",
        "run_app.bat",
        "start.bat",
        "launch.bat",
        "build_exe.bat",
        "deploy.bat",
        "start_app.bat",
        "一键启动.bat"
    ]
    
    # 复制核心文件
    for file_name in required_files:
        src_path = os.path.join(os.path.dirname(__file__), file_name)
        dst_path = os.path.join(backup_dir, file_name)
        
        if os.path.exists(src_path):
            try:
                if file_name == "inbound.db":
                    # 数据库文件需要特殊处理
                    shutil.copy2(src_path, dst_path)
                else:
                    shutil.copy2(src_path, dst_path)
                print(f"已复制: {file_name}")
            except Exception as e:
                print(f"复制文件 {file_name} 失败: {e}")
        else:
            print(f"文件不存在: {file_name}")
    
    # 复制静态文件目录
    static_src = os.path.join(os.path.dirname(__file__), "static")
    static_dst = os.path.join(backup_dir, "static")
    if os.path.exists(static_src):
        try:
            shutil.copytree(static_src, static_dst)
            print("已复制静态文件目录")
        except Exception as e:
            print(f"复制静态文件目录失败: {e}")
    else:
        print("静态文件目录不存在")
    
    # 创建zip压缩包
    zip_filename = f"project_backup_required_{timestamp}.zip"
    print(f"创建压缩包: {zip_filename}")
    
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(backup_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arc_path = os.path.relpath(file_path, backup_dir)
                zipf.write(file_path, arc_path)
                print(f"已添加到压缩包: {arc_path}")
    
    # 清理临时备份目录
    try:
        shutil.rmtree(backup_dir)
        print(f"已清理临时目录: {backup_dir}")
    except Exception as e:
        print(f"清理临时目录失败: {e}")
    
    print(f"备份完成! 压缩包: {zip_filename}")
    return zip_filename

if __name__ == "__main__":
    print("开始备份项目所有必要关联文件...")
    try:
        backup_file = backup_required_files()
        print(f"备份文件已创建: {backup_file}")
    except Exception as e:
        print(f"备份过程中出现错误: {e}")
        import traceback
        traceback.print_exc()