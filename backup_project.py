import os
import shutil
import zipfile
from datetime import datetime
import sys

def backup_project():
    """备份当前项目到zip文件"""
    # 获取当前工作目录
    project_dir = os.getcwd()
    project_name = os.path.basename(project_dir)
    
    # 生成备份文件名（包含时间戳）
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"backup_{project_name}_{timestamp}.zip"
    backup_path = os.path.join(os.path.dirname(project_dir), backup_filename)
    
    print(f"开始备份项目: {project_name}")
    print(f"备份路径: {backup_path}")
    
    # 创建zip文件
    with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(project_dir):
            # 排除备份目录本身，避免递归备份
            dirs[:] = [d for d in dirs if not d.startswith('backup_')]
            
            for file in files:
                # 排除备份脚本本身和备份文件
                if not file.startswith('backup_') and not file.endswith('.zip'):
                    file_path = os.path.join(root, file)
                    # 计算相对路径
                    rel_path = os.path.relpath(file_path, project_dir)
                    zipf.write(file_path, rel_path)
    
    print(f"备份完成: {backup_path}")
    print(f"备份文件大小: {os.path.getsize(backup_path) / (1024*1024):.2f} MB")
    return backup_path

if __name__ == '__main__':
    backup_project()