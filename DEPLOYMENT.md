# Inbound Recorder 部署指南

## 部署方式

本应用支持多种部署方式：

### 1. 本地直接运行（推荐）

#### Windows系统：
```bash
# 双击 start.bat 文件
# 或在命令行中运行：
start.bat
```

#### Linux/macOS系统：
```bash
# 在终端中运行：
chmod +x start.sh
./start.sh
```

### 2. Docker部署

#### 前提条件：
- 已安装Docker和Docker Compose

#### 部署步骤：
```bash
# 构建并启动容器
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止容器
docker-compose down
```

### 3. 手动部署

#### 前提条件：
- Python 3.7或更高版本
- pip包管理器

#### 部署步骤：
```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动应用
python single_app.py
```

## 环境变量配置

应用支持以下环境变量配置：

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| SECRET_KEY | your_secret_key_here_change_this_in_production | Flask应用密钥 |
| DATABASE_PATH | 自动检测 | 数据库文件路径 |
| HOST | 0.0.0.0 | 服务器监听地址 |
| PORT | 8080 | 服务器监听端口 |

## 数据持久化

- **本地部署**：数据存储在 `inbound.db` 文件中
- **Docker部署**：数据存储在 `./data/inbound.db` 文件中

## 访问应用

启动后，在浏览器中访问：
- 本地访问：http://localhost:8080
- 网络访问：http://[你的IP地址]:8080

## 安全建议

生产环境部署时，请务必：
1. 修改默认的SECRET_KEY
2. 限制HOST为特定IP地址（如127.0.0.1）
3. 使用反向代理（如Nginx）提供HTTPS支持
4. 定期备份数据库文件