#!/bin/bash

# Inbound Recorder 启动脚本

# 检查是否安装了Python
if ! command -v python3 &> /dev/null
then
    echo "未找到Python3，请先安装Python3"
    exit 1
fi

# 检查是否安装了pip
if ! command -v pip3 &> /dev/null
then
    echo "未找到pip3，请先安装pip3"
    exit 1
fi

# 安装依赖
echo "安装依赖..."
pip3 install -r requirements.txt

# 启动应用
echo "启动 Inbound Recorder 应用..."
echo "请在浏览器中访问 http://localhost:8080"
python3 single_app.py