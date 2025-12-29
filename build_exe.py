#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
构建单文件可执行程序
"""

import os
import sys
import subprocess
from datetime import datetime

def build_single_exe():
    """构建单文件可执行程序"""
    print("开始构建单文件可执行程序...")
    print("=" * 50)
    
    # 获取项目根目录
    project_root = os.path.dirname(os.path.abspath(__file__))
    print(f"项目根目录: {project_root}")
    
    # 切换到项目根目录
    os.chdir(project_root)
    
    # 构建命令
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",  # 单文件模式
        "--windowed",  # 无控制台窗口模式
        "--name", "InboundRecorder",
        "--icon", "NONE",
        "--add-data", "static;static",
        "--hidden-import", "openpyxl",
        "--hidden-import", "pytz",
        "--hidden-import", "sqlite3",
        "--clean",
        "single_app.py"
    ]
    
    print("构建命令:")
    print(" ".join(cmd))
    print("=" * 50)
    
    try:
        # 执行构建命令
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode == 0:
            print("✓ 构建成功!")
            print("标准输出:")
            print(result.stdout)
            
            # 获取生成的exe文件路径
            exe_path = os.path.join(project_root, "dist", "InboundRecorder.exe")
            if os.path.exists(exe_path):
                # 获取文件大小
                file_size = os.path.getsize(exe_path)
                file_size_mb = file_size / (1024 * 1024)
                
                print(f"\n生成的可执行文件: {exe_path}")
                print(f"文件大小: {file_size_mb:.2f} MB")
                
                # 获取构建时间
                build_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"构建完成时间: {build_time}")
                
                return exe_path
            else:
                print("✗ 未找到生成的可执行文件")
                return None
        else:
            print("✗ 构建失败!")
            print("错误输出:")
            print(result.stderr)
            return None
            
    except Exception as e:
        print(f"✗ 构建过程中出现异常: {e}")
        return None

def build_console_exe():
    """构建带控制台的单文件可执行程序"""
    print("开始构建带控制台的单文件可执行程序...")
    print("=" * 50)
    
    # 获取项目根目录
    project_root = os.path.dirname(os.path.abspath(__file__))
    print(f"项目根目录: {project_root}")
    
    # 切换到项目根目录
    os.chdir(project_root)
    
    # 构建命令
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",  # 单文件模式
        "--console",  # 带控制台窗口
        "--name", "InboundRecorderConsole",
        "--icon", "NONE",
        "--add-data", "static;static",
        "--hidden-import", "openpyxl",
        "--hidden-import", "pytz",
        "--hidden-import", "sqlite3",
        "--clean",
        "single_app.py"
    ]
    
    print("构建命令:")
    print(" ".join(cmd))
    print("=" * 50)
    
    try:
        # 执行构建命令
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode == 0:
            print("✓ 构建成功!")
            print("标准输出:")
            print(result.stdout)
            
            # 获取生成的exe文件路径
            exe_path = os.path.join(project_root, "dist", "InboundRecorderConsole.exe")
            if os.path.exists(exe_path):
                # 获取文件大小
                file_size = os.path.getsize(exe_path)
                file_size_mb = file_size / (1024 * 1024)
                
                print(f"\n生成的可执行文件: {exe_path}")
                print(f"文件大小: {file_size_mb:.2f} MB")
                
                # 获取构建时间
                build_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(f"构建完成时间: {build_time}")
                
                return exe_path
            else:
                print("✗ 未找到生成的可执行文件")
                return None
        else:
            print("✗ 构建失败!")
            print("错误输出:")
            print(result.stderr)
            return None
            
    except Exception as e:
        print(f"✗ 构建过程中出现异常: {e}")
        return None

if __name__ == "__main__":
    print("Inbound Recorder 单文件可执行程序构建工具")
    print("=" * 50)
    print("请选择构建选项:")
    print("1. 构建无控制台窗口的EXE文件（推荐）")
    print("2. 构建带控制台窗口的EXE文件")
    print("3. 退出")
    print("=" * 50)
    
    try:
        choice = input("请输入选项 (1/2/3): ").strip()
        
        if choice == "1":
            exe_path = build_single_exe()
            if exe_path:
                print(f"\n✓ 成功生成可执行文件: {exe_path}")
                print("此文件可独立运行，无需Python环境，便于携带和部署。")
            else:
                print("\n✗ 构建失败，请检查错误信息。")
                
        elif choice == "2":
            exe_path = build_console_exe()
            if exe_path:
                print(f"\n✓ 成功生成可执行文件: {exe_path}")
                print("此文件可独立运行，无需Python环境，便于携带和部署。")
            else:
                print("\n✗ 构建失败，请检查错误信息。")
                
        elif choice == "3":
            print("退出构建工具。")
            sys.exit(0)
            
        else:
            print("无效选项，请重新运行脚本并输入正确选项。")
            
    except KeyboardInterrupt:
        print("\n\n用户取消操作。")
    except Exception as e:
        print(f"\n发生错误: {e}")