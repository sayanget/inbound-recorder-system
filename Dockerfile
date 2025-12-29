# 使用官方Python运行时作为基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 复制requirements.txt并安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建数据卷以持久化数据
VOLUME ["/app/data"]

# 暴露端口
EXPOSE 8080

# 设置环境变量
ENV DATABASE_PATH=/app/data/inbound.db
ENV HOST=0.0.0.0
ENV PORT=8080

# 启动应用
CMD ["python", "single_app.py"]