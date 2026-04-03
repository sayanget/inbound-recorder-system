# Inbound Recorder 完整部署指南

## 项目概述

Inbound Recorder 是一个基于Python Flask的入库数据管理系统，用于跟踪和统计入库车辆信息、分拣数据以及生成各种统计报表。

## 系统架构

- **后端**: Python 3.7+
- **框架**: Flask
- **数据库**: SQLite (inbound.db)
- **前端**: HTML/CSS/JavaScript
- **图表库**: Chart.js

## 部署方式

### 方式一：快速部署（推荐）

#### Windows系统：
1. 确保已安装Python 3.7或更高版本
2. 双击 `启动应用.bat` 文件
3. 在浏览器中访问 `http://localhost:8080`

#### Linux/macOS系统：
1. 确保已安装Python 3.7或更高版本
2. 在终端中运行：
   ```bash
   chmod +x start.sh
   ./start.sh
   ```
3. 在浏览器中访问 `http://localhost:8080`

### 方式二：Docker部署

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

### 方式三：手动部署

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
| SECRET_KEY | your_secret_key_here_change_this_in_production | Flask应用密钥，生产环境必须修改 |
| DATABASE_PATH | 自动检测 | 数据库文件路径 |
| HOST | 0.0.0.0 | 服务器监听地址 |
| PORT | 8080 | 服务器监听端口 |

## 目录结构

```
inbound_recorder/
├── single_app.py          # 主应用文件
├── inbound.db             # 数据库文件
├── requirements.txt       # Python依赖列表
├── Dockerfile            # Docker镜像构建文件
├── docker-compose.yml    # Docker Compose配置文件
├── start.sh              # Linux/macOS启动脚本
├── start.bat             # Windows启动脚本
├── 启动应用.bat           # 简化版Windows启动脚本
├── DEPLOYMENT_FULL.md    # 本部署文档
├── static/               # 静态文件目录
│   ├── index.html        # 首页（数据概览）
│   ├── sorting.html      # 分拣录入页面
│   ├── history.html      # 历史查询页面
│   ├── statistics.html   # 统计数据页面
│   ├── admin.html        # 管理员页面
│   └── logs.html         # 日志页面
└── data/                 # Docker部署时的数据卷目录
```

## 数据持久化

### 本地部署
数据存储在项目根目录的 `inbound.db` 文件中。

### Docker部署
数据存储在 `./data/inbound.db` 文件中，通过Docker卷实现数据持久化。

## 访问应用

启动后，在浏览器中访问：
- 本地访问：http://localhost:8080
- 网络访问：http://[你的IP地址]:8080

## 用户权限系统

应用内置了用户权限管理系统：
- 默认管理员账号：admin
- 默认管理员密码：admin123
- 管理员可以配置用户权限，控制对各个页面的访问

## 安全建议

生产环境部署时，请务必：

1. **修改默认密钥**
   ```bash
   # 设置环境变量
   export SECRET_KEY="your_strong_secret_key_here"
   ```

2. **限制访问地址**
   ```bash
   # 仅允许本地访问
   export HOST="127.0.0.1"
   ```

3. **使用反向代理**
   - 推荐使用Nginx或Apache作为反向代理
   - 配置HTTPS支持

4. **定期备份数据**
   - 定期备份 `inbound.db` 文件
   - 建议每天备份一次

5. **防火墙配置**
   - 限制对应用端口的访问
   - 仅允许可信IP访问

## 故障排除

### 常见问题

1. **Python未找到**
   - 确保已安装Python 3.7或更高版本
   - 确保Python已添加到系统PATH环境变量

2. **依赖安装失败**
   - 检查网络连接
   - 尝试使用国内镜像源：
     ```bash
     pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
     ```

3. **端口被占用**
   - 修改PORT环境变量使用其他端口：
     ```bash
     export PORT=8081
     ```

4. **数据库锁定**
   - 确保只有一个应用实例在运行
   - 检查是否有其他进程正在访问数据库文件

### 日志查看

应用会在控制台输出运行日志，包括：
- 启动信息
- 请求日志
- 错误信息

## 升级维护

### 备份现有数据
```bash
# 备份数据库文件
cp inbound.db inbound.db.backup.$(date +%Y%m%d)
```

### 升级步骤
1. 备份现有数据和配置
2. 下载新版本文件
3. 替换除数据库外的所有文件
4. 启动应用验证

## 技术支持

如有任何问题，请联系开发者。