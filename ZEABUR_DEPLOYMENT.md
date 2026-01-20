# Zeabur 部署指南

## 当前项目状态分析

### ✅ 已具备的条件
1. **Flask 应用**: `single_app.py` 是主应用文件
2. **依赖文件**: `requirements.txt` 已存在
3. **Dockerfile**: 已有基础 Dockerfile
4. **环境变量支持**: 代码已支持 `HOST`, `PORT`, `DATABASE_PATH` 等环境变量

### ⚠️ 需要调整的问题

## 必需的调整

### 1. 数据库迁移到 PostgreSQL (Neon)

**问题**: 当前使用 SQLite，Zeabur 容器重启会丢失数据

**解决方案**: 已完成 Neon PostgreSQL 部署，需要修改代码

#### 1.1 更新 `requirements.txt`

```txt
Flask==2.3.3
openpyxl==3.1.2
pytz==2023.3
schedule==1.2.0
psycopg2-binary==2.9.9
python-dotenv==1.0.0
```

#### 1.2 创建数据库连接模块 `database.py`

```python
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

# 从环境变量获取数据库连接信息
DATABASE_URL = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')

@contextmanager
def get_db_connection():
    """获取数据库连接的上下文管理器"""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def execute_query(query, params=None, fetch_one=False, fetch_all=False):
    """执行数据库查询"""
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, params or ())
            
            if fetch_one:
                return cursor.fetchone()
            elif fetch_all:
                return cursor.fetchall()
            else:
                return cursor.rowcount
```

#### 1.3 修改 `single_app.py` 中的数据库操作

需要将所有 `sqlite3` 操作替换为 PostgreSQL 操作:

**主要变更点**:
- `sqlite3.connect()` → `psycopg2.connect()`
- `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL PRIMARY KEY`
- `DATETIME DEFAULT CURRENT_TIMESTAMP` → `TIMESTAMP DEFAULT CURRENT_TIMESTAMP`
- `?` 占位符 → `%s` 占位符
- `BOOLEAN` 类型: SQLite 使用 0/1，PostgreSQL 使用 true/false

### 2. 修改 Dockerfile

**当前问题**: 
- 使用 `debug=True` 不适合生产环境
- 缺少生产级 WSGI 服务器

**优化后的 Dockerfile**:

```dockerfile
# 使用官方Python运行时作为基础镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# 复制requirements.txt并安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8080

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV HOST=0.0.0.0
ENV PORT=8080

# 使用 gunicorn 启动应用
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "4", "--timeout", "120", "single_app:app"]
```

### 3. 添加 `gunicorn` 到依赖

更新 `requirements.txt`:

```txt
Flask==2.3.3
openpyxl==3.1.2
pytz==2023.3
schedule==1.2.0
psycopg2-binary==2.9.9
python-dotenv==1.0.0
gunicorn==21.2.0
```

### 4. 修改应用启动方式

修改 `single_app.py` 底部:

```python
if __name__ == "__main__":
    init_db()
    
    # 启动每日重置检查线程
    reset_thread = threading.Thread(target=daily_reset_check, daemon=True)
    reset_thread.start()
    
    # 从环境变量获取主机和端口配置
    host = os.environ.get('HOST', HOST)
    port = int(os.environ.get('PORT', PORT))
    
    # 生产环境使用 gunicorn，开发环境使用 Flask 内置服务器
    is_production = os.environ.get('ENVIRONMENT', 'development') == 'production'
    
    print(f"Starting server on {host}:{port}")
    if is_production:
        # Gunicorn 会处理启动
        pass
    else:
        app.run(debug=True, host=host, port=port)
```

### 5. 环境变量配置

在 Zeabur 中需要配置以下环境变量:

| 变量名 | 值 | 说明 |
|--------|-----|------|
| `DATABASE_URL` | `postgresql://neondb_owner:npg_G1pxCJTigOK2@ep-green-meadow-afwsztqi-pooler.c-2.us-west-2.aws.neon.tech/neondb?sslmode=require` | Neon 数据库连接串 |
| `SECRET_KEY` | `<随机生成的密钥>` | Flask session 密钥 |
| `ENVIRONMENT` | `production` | 运行环境 |
| `PORT` | `8080` | 端口号 (Zeabur 会自动设置) |
| `HOST` | `0.0.0.0` | 监听地址 |

### 6. Session 存储调整

**问题**: 当前使用文件系统存储 session，多实例部署会有问题

**解决方案**: 使用 Flask-Session 和 PostgreSQL 存储

```python
from flask_session import Session
import redis

# Session 配置
app.config['SESSION_TYPE'] = 'redis'  # 或使用 'sqlalchemy'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'inbound_app:'
app.config['SESSION_REDIS'] = redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379'))

Session(app)
```

或者使用 PostgreSQL 存储:

```python
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy

app.config['SESSION_TYPE'] = 'sqlalchemy'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SESSION_SQLALCHEMY_TABLE'] = 'sessions'

db = SQLAlchemy(app)
app.config['SESSION_SQLALCHEMY'] = db
Session(app)
```

## Zeabur 部署步骤

### 方式一: 通过 GitHub 部署 (推荐)

1. **推送代码到 GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit for Zeabur deployment"
   git remote add origin <your-github-repo-url>
   git push -u origin main
   ```

2. **在 Zeabur 创建项目**
   - 登录 [Zeabur](https://zeabur.com)
   - 点击 "New Project"
   - 选择 "Deploy from GitHub"
   - 选择你的仓库

3. **配置环境变量**
   - 在 Zeabur 项目设置中添加上述环境变量

4. **部署**
   - Zeabur 会自动检测 Dockerfile 并部署

### 方式二: 使用 Zeabur CLI

```bash
# 安装 Zeabur CLI
npm install -g @zeabur/cli

# 登录
zeabur login

# 部署
zeabur deploy
```

## 验证部署

部署完成后:

1. **检查日志**: 在 Zeabur 控制台查看应用日志
2. **测试连接**: 访问 Zeabur 提供的 URL
3. **数据库连接**: 确认能正常读写 Neon 数据库
4. **功能测试**: 测试登录、数据录入等功能

## 常见问题

### 1. 端口绑定失败

**问题**: `Address already in use`

**解决**: Zeabur 会自动设置 `PORT` 环境变量，确保代码使用该变量

### 2. 数据库连接超时

**问题**: `connection timeout`

**解决**: 
- 检查 Neon 数据库是否在运行
- 确认 `DATABASE_URL` 环境变量正确
- 检查网络连接

### 3. Session 丢失

**问题**: 用户频繁需要重新登录

**解决**: 使用 Redis 或 PostgreSQL 存储 session，不要使用文件系统

## 性能优化建议

1. **启用 CDN**: 静态文件使用 CDN 加速
2. **数据库连接池**: 使用 `psycopg2.pool` 管理连接
3. **缓存**: 使用 Redis 缓存频繁查询的数据
4. **日志**: 配置结构化日志，便于问题排查

## 回滚策略

如果部署出现问题:

1. **Zeabur 控制台**: 可以回滚到之前的部署版本
2. **GitHub**: 回退代码提交
3. **数据库备份**: 定期备份 Neon 数据库

## 下一步

- [ ] 修改代码以支持 PostgreSQL
- [ ] 更新 Dockerfile 和 requirements.txt
- [ ] 配置环境变量
- [ ] 推送到 GitHub
- [ ] 在 Zeabur 部署
- [ ] 测试验证
