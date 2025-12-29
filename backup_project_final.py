import os
import zipfile
from datetime import datetime
import shutil

def create_project_backup():
    # 获取当前时间作为备份文件名的一部分
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"project_backup_complete_{timestamp}.zip"
    
    # 定义需要备份的重要文件和目录
    important_files = [
        "single_app.py",
        "inbound.db",
        "requirements.txt",
        "Dockerfile",
        "docker-compose.yml",
        "DEPLOYMENT.md",
        "DEPLOYMENT_FULL.md",
        "build_exe.bat",
        "launch.bat",
        "start.bat",
        "start_app.bat",
        "run_app.bat",
        "start.sh",
        "single_app.spec",
        "exclude.txt"
    ]
    
    important_dirs = [
        "static",
        "deployment_package",
        "improved_deployment_package"
    ]
    
    # 创建备份文件
    with zipfile.ZipFile(backup_filename, 'w', zipfile.ZIP_DEFLATED) as backup_zip:
        # 添加重要文件
        for file in important_files:
            if os.path.exists(file):
                backup_zip.write(file)
                print(f"Added file: {file}")
            else:
                print(f"File not found: {file}")
        
        # 添加重要目录
        for directory in important_dirs:
            if os.path.exists(directory):
                for root, dirs, files in os.walk(directory):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # 避免添加备份文件到备份中
                        if not file_path.endswith('.zip'):
                            backup_zip.write(file_path)
                            print(f"Added file: {file_path}")
            else:
                print(f"Directory not found: {directory}")
    
    print(f"\nComplete backup created successfully: {backup_filename}")
    return backup_filename

if __name__ == "__main__":
    create_project_backup()