import sqlite3
from flask import Flask, request, jsonify, send_file, session, redirect
import os
import sys
from datetime import datetime, timedelta
import pytz
import threading
import time
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
import json
import hashlib
import functools

# 数据库抽象层 - 自动适配 SQLite/PostgreSQL
from database import get_db_connection, convert_sql, get_placeholder, USE_POSTGRES

app = Flask(__name__)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'inbound_app:'

# 获取正确的数据库路径
def get_db_path():
    # 如果是打包后的exe环境，数据库在同级目录下
    if getattr(sys, 'frozen', False):
        # 打包后的exe环境
        return os.path.join(os.path.dirname(sys.executable), 'inbound.db')
    else:
        # 开发环境
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'inbound.db')

# 获取正确的静态文件目录
def get_static_dir():
    if getattr(sys, 'frozen', False):
        # 打包后的exe环境 - 静态文件被打包到exe中，需要使用特殊方法访问
        # PyInstaller会将数据文件放在_sys_meipass目录中
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, 'static')
        else:
            # 备用方案
            return os.path.join(os.path.dirname(sys.executable), 'static')
    else:
        # 开发环境 - 使用脚本所在目录的static子目录
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

# 数据库连接辅助函数 - 兼容 SQLite 和 PostgreSQL
def get_db():
    """获取数据库连接 - 自动适配 SQLite/PostgreSQL"""
    if USE_POSTGRES:
        import psycopg2
        # 使用 DictCursor 替代 RealDictCursor
        # DictCursor 返回的行对象同时支持 索引访问(row[0]) 和 键访问(row['id'])
        # 这完美兼容了我们现有的代码 (混合使用了两种访问方式)
        from psycopg2.extras import DictCursor
        from database import DATABASE_URL
        
        # 创建原始连接
        original_conn = psycopg2.connect(DATABASE_URL, cursor_factory=DictCursor)
        
        # 创建连接包装类
        class ConnectionWrapper:
            def __init__(self, conn):
                self._conn = conn
            
            def cursor(self, *args, **kwargs):
                cur = self._conn.cursor(*args, **kwargs)
                original_execute = cur.execute
                
                def execute_wrapper(query, params=None):
                    # 自动转换 ? 为 %s
                    converted_query = query.replace('?', '%s')
                    return original_execute(converted_query, params)
                
                cur.execute = execute_wrapper
                return cur
            
            def commit(self):
                return self._conn.commit()
            
            def rollback(self):
                return self._conn.rollback()
            
            def close(self):
                return self._conn.close()
            
            def __enter__(self):
                return self
            
            def __exit__(self, exc_type, exc_val, exc_tb):
                if exc_type:
                    self._conn.rollback()
                else:
                    self._conn.commit()
                self._conn.close()
        
        return ConnectionWrapper(original_conn)
    else:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        # 使用 Row 工厂,使 SQLite 结果可以像字典一样访问
        conn.row_factory = sqlite3.Row
        return conn

def convert_query_placeholders(query):
    """转换 SQL 查询占位符 - SQLite 的 ? 转为 PostgreSQL 的 %s"""
    if USE_POSTGRES:
        return query.replace('?', '%s')
    return query

# 定义洛杉矶时区
LA_TZ = pytz.timezone('America/Los_Angeles')

def round_to_ten_thousand(value):
    """
    将数值向下取整到万位(千百十个位全部为0)
    例如: 1,232,342 -> 1,230,000
         987,654 -> 980,000
         45,678 -> 40,000
    """
    if value is None:
        return 0
    return (int(value) // 10000) * 10000

# 从环境变量获取配置，如果没有则使用默认值
app.secret_key = os.environ.get('SECRET_KEY', 'your_secret_key_here_change_this_in_production')

# Session configuration
app.config['SESSION_COOKIE_SECURE'] = False  # 在开发环境中设为False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# 数据库路径配置
DB_PATH = os.environ.get('DATABASE_PATH') or get_db_path()

# 服务器配置
HOST = os.environ.get('HOST', '0.0.0.0')
PORT = int(os.environ.get('PORT', 8080))

# 应用初始化标志
_app_initialized = False

def initialize_app():
    """初始化应用 - 确保在 Gunicorn 环境下也能正确初始化"""
    global _app_initialized
    if not _app_initialized:
        try:
            print("[应用初始化] 开始初始化数据库...")
            init_db()
            print("[应用初始化] 数据库初始化完成")
            _app_initialized = True
        except Exception as e:
            print(f"[应用初始化] 错误: {e}")
            import traceback
            traceback.print_exc()
            # 不要抛出异常,让应用继续启动
            # 这样可以看到更详细的错误信息

# 获取正确的静态文件目录
def get_static_dir():
    if getattr(sys, 'frozen', False):
        # 打包后的exe环境 - 静态文件被打包到exe中，需要使用特殊方法访问
        # PyInstaller会将数据文件放在_sys_meipass目录中
        if hasattr(sys, '_MEIPASS'):
            return os.path.join(sys._MEIPASS, 'static')
        else:
            # 备用方案
            return os.path.join(os.path.dirname(sys.executable), 'static')
    else:
        # 开发环境 - 使用脚本所在目录的static子目录
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

# 定义洛杉矶时区
LA_TZ = pytz.timezone('America/Los_Angeles')

def round_to_ten_thousand(value):
    """
    将数值向下取整到万位(千百十个位全部为0)
    例如: 1,232,342 -> 1,230,000
         987,654 -> 980,000
         45,678 -> 40,000
    """
    if value is None:
        return 0
    return (int(value) // 10000) * 10000

def init_db():
    """初始化数据库 - 自动适配 SQLite/PostgreSQL"""
    # 使用数据库抽象层
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 检查表是否存在 (PostgreSQL 和 SQLite 语法不同)
        if USE_POSTGRES:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'inbound_records'
                )
            """)
            result = cursor.fetchone()
            # PostgreSQL RealDictCursor 返回字典,需要用列名访问
            need = not result['exists'] if USE_POSTGRES else not result[0]
        else:
            need = not os.path.exists(DB_PATH)
        
        if need:
            # 创建入库记录表
            sql = convert_sql("""CREATE TABLE inbound_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dock_no INTEGER,
                vehicle_type TEXT,
                vehicle_no TEXT,
                unit TEXT,
                load_amount INTEGER,
                pieces INTEGER,
                time_slot TEXT,
                shift_type TEXT,
                remark TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );""")
            cursor.execute(sql)
        
            # 创建分拣记录表
            sql = convert_sql("""CREATE TABLE sorting_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sorting_time DATETIME,
                pieces INTEGER,
                remark TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );""")
            cursor.execute(sql)
            
            # 创建操作日志表
            sql = convert_sql("""CREATE TABLE operation_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_type TEXT,
                table_name TEXT,
                record_id INTEGER,
                old_data TEXT,
                new_data TEXT,
                operator TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );""")
            cursor.execute(sql)
            
            # 创建揽收预估数据表
            sql = convert_sql("""CREATE TABLE pickup_forecast (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                forecast_date DATE NOT NULL,
                forecast_amount INTEGER NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );""")
            cursor.execute(sql)
            
            # 创建用户表
            sql = convert_sql("""CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );""")
            cursor.execute(sql)
            
            # 创建用户权限表
            sql = convert_sql("""CREATE TABLE user_permissions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                page_name TEXT NOT NULL,
                can_view BOOLEAN DEFAULT 0,
                can_edit BOOLEAN DEFAULT 0,
                can_delete BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            );""")
            cursor.execute(sql)
        
            # 插入默认管理员用户 (用户名: admin, 密码: admin123)
            import hashlib
            admin_password = hashlib.sha256("admin123".encode()).hexdigest()
            placeholder = get_placeholder()
            cursor.execute(f"INSERT INTO users (username, password_hash, role) VALUES ({placeholder}, {placeholder}, {placeholder})",
                        ("admin", admin_password, "admin"))
            
            # 为管理员用户设置默认权限
            cursor.execute(f"SELECT id FROM users WHERE username = {placeholder}", ("admin",))
            result = cursor.fetchone()
            admin_user_id = result[0] if USE_POSTGRES else result[0]
            
            # 管理员拥有所有页面的所有权限
            pages = ['index', 'sorting', 'history', 'statistics', 'logs']
            for page in pages:
                cursor.execute(f"""INSERT INTO user_permissions 
                    (user_id, page_name, can_view, can_edit, can_delete) 
                    VALUES ({placeholder}, {placeholder}, 1, 1, 1)""", 
                    (admin_user_id, page))
        else:
            # 如果数据库已存在，检查并创建用户表和权限表（如果不存在）
            if USE_POSTGRES:
                cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'users')")
                result = cursor.fetchone()
                table_exists = result['exists']
            else:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
                table_exists = cursor.fetchone() is not None
            
            if not table_exists:
                # 创建用户表
                sql = convert_sql("""CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT DEFAULT 'user',
                    is_active BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );""")
                cursor.execute(sql)
                
                # 创建用户权限表
                sql = convert_sql("""CREATE TABLE user_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    page_name TEXT NOT NULL,
                    can_view BOOLEAN DEFAULT 0,
                    can_edit BOOLEAN DEFAULT 0,
                    can_delete BOOLEAN DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                );""")
                cursor.execute(sql)
                
                # 插入默认管理员用户
                import hashlib
                admin_password = hashlib.sha256("admin123".encode()).hexdigest()
                placeholder = get_placeholder()
                cursor.execute(f"INSERT INTO users (username, password_hash, role) VALUES ({placeholder}, {placeholder}, {placeholder})",
                            ("admin", admin_password, "admin"))
                
                # 为管理员用户设置默认权限
                cursor.execute(f"SELECT id FROM users WHERE username = {placeholder}", ("admin",))
                result = cursor.fetchone()
                admin_user_id = result['id'] if USE_POSTGRES else result[0]
                
                # 管理员拥有所有页面的所有权限
                pages = ['index', 'sorting', 'history', 'statistics', 'logs']
                for page in pages:
                    cursor.execute(f"""INSERT INTO user_permissions 
                        (user_id, page_name, can_view, can_edit, can_delete) 
                        VALUES ({placeholder}, {placeholder}, 1, 1, 1)""", 
                        (admin_user_id, page))
            
            # 检查并创建揽收预估数据表（如果不存在）
            if USE_POSTGRES:
                cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'pickup_forecast')")
                result = cursor.fetchone()
                table_exists = result['exists']
            else:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pickup_forecast'")
                table_exists = cursor.fetchone() is not None
            
            if not table_exists:
                sql = convert_sql("""CREATE TABLE pickup_forecast (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    forecast_date DATE NOT NULL,
                    forecast_amount INTEGER NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );""")
                cursor.execute(sql)
                
                # 创建分拣记录表
                sql = convert_sql("""CREATE TABLE IF NOT EXISTS sorting_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sorting_time DATE,
                    pieces INTEGER,
                    remark TEXT,
                    time_slot TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );""")
                cursor.execute(sql)

def convert_utc_to_la(utc_time_str):
    """直接返回时间字符串，因为数据库中存储的已经是洛杉矶时间"""
    return utc_time_str

# 检查用户权限
def check_user_permission(page_name, permission_type='view'):
    if 'user_id' not in session:
        return False
    
    user_id = session['user_id']
    
    # 查询用户权限
    conn = get_db()
    query = f"""
        SELECT up.can_{permission_type}
        FROM user_permissions up
        WHERE up.user_id = ? AND up.page_name = ?
    """
    cursor = conn.cursor(); cursor.execute(query, (user_id, page_name))
    result = cursor.fetchone()
    conn.close()
    
    return result and (result[f'can_{permission_type}'] if USE_POSTGRES else result[0])

def daily_reset_check():
    """每日重置检查函数"""
    while True:
        try:
            # 获取洛杉矶当前时间
            la_now = datetime.now(LA_TZ)
            
            # 如果是午夜（0点）附近，执行重置
            if la_now.hour == 0 and la_now.minute == 0:
                print(f"执行每日重置: {la_now}")
                perform_daily_reset()
                
                # 等待一分钟，避免重复执行
                time.sleep(60)
            else:
                # 每分钟检查一次
                time.sleep(60)
        except Exception as e:
            print(f"每日重置检查出错: {e}")
            time.sleep(60)

def perform_daily_reset():
    """执行每日重置 - 仅记录日志，不删除历史数据"""
    try:
        print("每日重置检查完成 - 历史数据已永久保存")
    except Exception as e:
        print(f"每日重置执行出错: {e}")


@app.route('/')
def index():
    # 检查用户权限，所有用户都需要登录
    if 'user_id' not in session:
        return redirect('/login')
    
    # 已登录用户检查权限
    if not check_page_permission('index'):
        return redirect('/no_permission')
    
    # 有权限则返回主页
    static_dir = get_static_dir()
    file_path = os.path.join(static_dir, 'index.html')
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content, 200, {'Content-Type': 'text/html; charset=utf-8'}
    else:
        return f"File not found: {file_path}", 404

@app.route('/sorting')
def sorting():
    # 检查用户权限
    if 'user_id' not in session:
        return redirect('/login')
    
    if not check_page_permission('sorting'):
        return redirect('/no_permission')
    
    # 返回分拣录入页面
    static_dir = get_static_dir()
    file_path = os.path.join(static_dir, 'sorting.html')
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content, 200, {'Content-Type': 'text/html; charset=utf-8'}
    else:
        return f"File not found: {file_path}", 404

@app.route('/history')
def history():
    # 检查用户权限
    if 'user_id' not in session:
        return redirect('/login')
    
    if not check_page_permission('history'):
        return redirect('/no_permission')
    
    # 返回历史查询页面
    static_dir = get_static_dir()
    file_path = os.path.join(static_dir, 'history.html')
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content, 200, {'Content-Type': 'text/html; charset=utf-8'}
    else:
        return f"File not found: {file_path}", 404

@app.route('/statistics')
def statistics():
    # 检查用户权限
    if 'user_id' not in session:
        return redirect('/login')
    
    if not check_page_permission('statistics'):
        return redirect('/no_permission')
    
    # 返回统计数据页面
    static_dir = get_static_dir()
    file_path = os.path.join(static_dir, 'statistics.html')
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content, 200, {'Content-Type': 'text/html; charset=utf-8'}
    else:
        return f"File not found: {file_path}", 404

@app.route('/debug_pallet_chart.html')
def debug_pallet_chart():
    # 返回调试页面
    static_dir = get_static_dir()
    file_path = os.path.join(static_dir, 'debug_pallet_chart.html')
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content, 200, {'Content-Type': 'text/html; charset=utf-8'}
    else:
        return f"File not found: {file_path}", 404

@app.route('/pallet_chart_test.html')
def pallet_chart_test():
    # 返回托盘图表测试页面
    static_dir = get_static_dir()
    file_path = os.path.join(static_dir, 'pallet_chart_test.html')
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content, 200, {'Content-Type': 'text/html; charset=utf-8'}
    else:
        return f"File not found: {file_path}", 404

@app.route('/logs')
def logs_page():
    # 检查用户权限
    if 'user_id' not in session:
        return jsonify({'error': '未登录'}), 401
    
    if not check_user_permission('logs', 'view'):
        return jsonify({'error': '权限不足'}), 403
    
    # 返回操作日志查询页面
    static_dir = get_static_dir()
    file_path = os.path.join(static_dir, 'logs.html')
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content, 200, {'Content-Type': 'text/html; charset=utf-8'}
    else:
        return f"File not found: {file_path}", 404

# 登录页面
@app.route('/login')
def login_page():
    # 返回简单的登录页面
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>登录</title>
        <style>
            body { font-family: Arial, sans-serif; background-color: #f5f7fb; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
            .login-container { background: white; padding: 2rem; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 300px; }
            h2 { text-align: center; margin-bottom: 1.5rem; color: #333; }
            .form-group { margin-bottom: 1rem; }
            label { display: block; margin-bottom: 0.5rem; color: #555; }
            input { width: 100%; padding: 0.75rem; border: 1px solid #ddd; border-radius: 4px; box-sizing: border-box; }
            button { width: 100%; padding: 0.75rem; background-color: #4361ee; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 1rem; }
            button:hover { background-color: #3a56d4; }
            .error { color: #f72585; text-align: center; margin-top: 1rem; }
        </style>
    </head>
    <body>
        <div class="login-container">
            <h2>用户登录</h2>
            <form id="loginForm">
                <div class="form-group">
                    <label for="username">用户名:</label>
                    <input type="text" id="username" name="username" required>
                </div>
                <div class="form-group">
                    <label for="password">密码:</label>
                    <input type="password" id="password" name="password" required>
                </div>
                <button type="submit">登录</button>
                <div id="errorMessage" class="error"></div>
            </form>
        </div>
        <script>
            document.getElementById('loginForm').addEventListener('submit', function(e) {
                e.preventDefault();
                
                const username = document.getElementById('username').value;
                const password = document.getElementById('password').value;
                const errorMessage = document.getElementById('errorMessage');
                
                // 清除之前的错误消息
                errorMessage.textContent = '';
                
                // 简单的前端验证
                if (!username || !password) {
                    errorMessage.textContent = '请输入用户名和密码';
                    return;
                }
                
                fetch('/api/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ username, password })
                })
                .then(response => {
                    // 检查响应状态
                    if (!response.ok) {
                        throw new Error('HTTP error ' + response.status);
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.success) {
                        window.location.href = '/';
                    } else {
                        errorMessage.textContent = data.error || '登录失败';
                    }
                })
                .catch(error => {
                    console.error('登录请求出错:', error);
                    errorMessage.textContent = '网络错误，请稍后重试 (' + error.message + ')';
                });
            });
        </script>
    </body>
    </html>
    ''', 200, {'Content-Type': 'text/html; charset=utf-8'}

# 管理员后台页面
@app.route('/admin')
def admin_page():
    # 返回管理员后台页面
    static_dir = get_static_dir()
    file_path = os.path.join(static_dir, 'admin.html')
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content, 200, {'Content-Type': 'text/html; charset=utf-8'}
    else:
        return f"File not found: {file_path}", 404

# 无权限提示页面
@app.route('/no_permission')
def no_permission():
    static_dir = get_static_dir()
    file_path = os.path.join(static_dir, 'no_permission.html')
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return content, 200, {'Content-Type': 'text/html; charset=utf-8'}
    else:
        return f"File not found: {file_path}", 404

# 检查重复记录的API端点
@app.route('/api/check_duplicate', methods=['POST'])
def check_duplicate():
    data = request.json
    dock_no = data.get("dock_no")
    vehicle_type = data.get("vehicle_type")
    
    # Car 和 Van 不检查重复
    if vehicle_type in ['Car', 'Van']:
        return jsonify({"is_duplicate": False})
    
    if not dock_no:
        return jsonify({"is_duplicate": False})
    
    conn = get_db()
    cursor = conn.cursor(); cursor.execute("""
        SELECT id, vehicle_type, vehicle_no, created_at 
        FROM inbound_records 
        WHERE dock_no = ? AND vehicle_type NOT IN ('Car', 'Van')
        ORDER BY created_at DESC 
        LIMIT 1
    """, (dock_no,))
    
    last_record = cursor.fetchone()
    conn.close()
    
    if not last_record:
        return jsonify({"is_duplicate": False})
    
    # 计算时间差
    try:
        last_time = datetime.strptime(last_record[3], '%Y-%m-%d %H:%M:%S')
        current_time = datetime.now()
        time_diff_seconds = (current_time - last_time).total_seconds()
        time_diff_minutes = int(time_diff_seconds / 60)
        
        if time_diff_minutes < 25:
            return jsonify({
                "is_duplicate": True,
                "time_diff_minutes": time_diff_minutes,
                "last_record": {
                    "id": last_record[0],
                    "vehicle_type": last_record[1],
                    "vehicle_no": last_record[2] or "无",
                    "created_at": last_record[3]
                }
            })
    except Exception as e:
        print(f"检查重复记录时出错: {e}")
        return jsonify({"is_duplicate": False})
    
    return jsonify({"is_duplicate": False})

@app.route('/api/record', methods=['POST'])
def record():
    data = request.json
    vt = data.get("vehicle_type","")
    if vt=="26英尺":
        data["unit"]="托盘"
        data["load_amount"]=12
        data["pieces"]=12*344
    elif vt=="Car":
        data["unit"]="篮筐"
        data["load_amount"]=1
        data["pieces"]=1*172
    elif vt=="Van":
        data["unit"]="篮筐"
        data["load_amount"]=9
        data["pieces"]=9*172
    elif vt=="53英尺":
        data.setdefault("unit","托盘")
        # 当车辆类型为53英尺时，如果没有输入装载量，则默认为24托盘
        load_amount = data.get("load_amount", 0)
        if not load_amount or load_amount == 0:
            # 默认24托盘
            data["load_amount"] = 24
            data["pieces"] = 24 * 344  # 8256件
        elif load_amount > 0:
            # 用户输入了装载量，自动计算件数
            data["pieces"] = load_amount * 344
        # 如果已有件数但没有装载量，也可以反向计算装载量
        elif data.get("pieces") and data["pieces"] > 0:
            data["load_amount"] = data["pieces"] // 344


    conn=get_db()
    # 获取当前系统时间
    current_time = datetime.now()
    current_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
    
    # 自动判断班次类型:17点之前是早班,17点之后是晚班
    if current_time.hour < 17:
        shift_type = "早班"
    else:
        shift_type = "晚班"
    
    # 自动填充时间段:如果用户没有提供time_slot,则使用系统当前时间的小时部分
    time_slot = data.get("time_slot")
    if not time_slot or time_slot == "" or time_slot is None:
        time_slot = str(current_time.hour)
    
    # 修正后的时长计算逻辑:
    # 当新车到达时,更新同一道口上一台车的时长
    # 新车的时长为NULL(因为还不知道下一台车什么时候来)
    # 注意: Car和Van不占用道口,不计算时长
    dock_no = data.get("dock_no")
    vehicle_type = data.get("vehicle_type")
    
    # 只有非Car/Van车型才计算道口占用时长
    if dock_no and vehicle_type not in ['Car', 'Van']:
        # 查询同一道口的最后一条非Car/Van记录
        cursor = conn.cursor(); cursor.execute("""
            SELECT id, created_at, vehicle_type FROM inbound_records 
            WHERE dock_no = ? AND vehicle_type NOT IN ('Car', 'Van')
            ORDER BY created_at DESC 
            LIMIT 1
        """, (dock_no,))
        last_record = cursor.fetchone()
        
        if last_record:
            try:
                last_id = last_record[0]
                last_vehicle_type = last_record[2]
                # 解析上一条记录的时间
                last_time = datetime.strptime(last_record[1], '%Y-%m-%d %H:%M:%S')
                # 计算上一台车的占用时长(分钟)
                time_diff_seconds = (current_time - last_time).total_seconds()
                last_duration = int(time_diff_seconds / 60)
                # 确保时长不为负数
                if last_duration < 0:
                    last_duration = 0
                
                # 更新上一条记录的时长
                conn.cursor().execute("""
                    UPDATE inbound_records 
                    SET duration = ? 
                    WHERE id = ?
                """, (last_duration, last_id))
                print(f"[INFO] 更新记录ID {last_id} ({last_vehicle_type}) 的时长为 {last_duration} 分钟")
            except Exception as e:
                print(f"计算并更新上一条记录时长时出错: {e}")
    
    # 插入新记录,时长为NULL(车刚到,还不知道会占用多久)
    conn.cursor().execute("""INSERT INTO inbound_records
        (dock_no, vehicle_type, vehicle_no, unit, load_amount, pieces, time_slot, shift_type, remark, created_at, duration)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)""",
        (data.get("dock_no"), data.get("vehicle_type"), data.get("vehicle_no"),
         data.get("unit"), data.get("load_amount"), data.get("pieces"),
         time_slot, shift_type, data.get("remark"), current_time_str))
    conn.commit()
    conn.close()
    return jsonify({"success":True})

@app.route('/api/record/<int:record_id>', methods=['PUT'])
def update_record(record_id):
    print(f"[DEBUG] PUT /api/record/{record_id} 被调用")
    data = request.json
    print(f"[DEBUG] 接收到的数据: {data}")
    
    # 获取当前系统时间并自动判断班次类型
    current_time = datetime.now()
    
    # 自动判断班次类型：17点之前是早班，17点之后是晚班
    if current_time.hour < 17:
        shift_type = "早班"
    else:
        shift_type = "晚班"
    
    # 对于53英尺车辆，如果没有输入装载量，则默认为24托盘
    vt = data.get("vehicle_type", "")
    if vt == "53英尺":
        data.setdefault("unit", "托盘")
        load_amount = data.get("load_amount", 0)
        if not load_amount or load_amount == 0:
            # 默认24托盘
            data["load_amount"] = 24
            data["pieces"] = 24 * 344  # 8256件
        elif load_amount > 0:
            # 用户输入了装载量，自动计算件数
            data["pieces"] = load_amount * 344
        # 如果已有件数但没有装载量，也可以反向计算装载量
        elif data.get("pieces") and data["pieces"] > 0:
            data["load_amount"] = data["pieces"] // 344

    
    conn = None
    try:
        conn = get_db()
        print(f"[DEBUG] 数据库连接成功: {DB_PATH}")
        
        # 获取修改前的数据
        old_record_cur = conn.cursor(); old_record_cur.execute("SELECT * FROM inbound_records WHERE id=?", (record_id,))
        old_record = old_record_cur.fetchone()
        print(f"[DEBUG] 原始记录: {old_record}")
        
        cursor = conn.cursor(); cursor.execute("""UPDATE inbound_records SET
            dock_no=?, vehicle_type=?, vehicle_no=?, unit=?, load_amount=?, pieces=?, time_slot=?, shift_type=?, remark=?, duration=?
            WHERE id=?""",
            (data.get("dock_no"), data.get("vehicle_type"), data.get("vehicle_no"),
             data.get("unit"), data.get("load_amount"), data.get("pieces"),
             data.get("time_slot"), shift_type, data.get("remark"), data.get("duration"), record_id))
        
        print(f"[DEBUG] 更新操作影响的行数: {cursor.rowcount}")
        
        # 如果记录被成功更新，记录日志
        if cursor.rowcount > 0:
            # 获取修改后的数据
            new_record_cur = conn.cursor(); new_record_cur.execute("SELECT * FROM inbound_records WHERE id=?", (record_id,))
            new_record = new_record_cur.fetchone()
            
            # 记录操作日志
            column_names = [description[0] for description in old_record_cur.description]
            old_data = dict(zip(column_names, old_record)) if old_record else {}
            new_data = dict(zip(column_names, new_record)) if new_record else {}
            
            # 删除游标对象，避免序列化错误
            if 'cursor' in old_data:
                del old_data['cursor']
            if 'cursor' in new_data:
                del new_data['cursor']
            
            conn.cursor().execute("""INSERT INTO operation_logs 
                (operation_type, table_name, record_id, old_data, new_data)
                VALUES (?, ?, ?, ?, ?)""",
                ('edit', 'inbound_records', record_id, 
                 json.dumps(old_data, default=str), 
                 json.dumps(new_data, default=str)))
            
            conn.commit()
            if conn:
                conn.close()
            print("[DEBUG] 记录更新成功")
            return jsonify({"success": True})
        else:
            conn.commit()
            if conn:
                conn.close()
            print("[DEBUG] 记录未找到")
            return jsonify({"success": False, "error": "记录未找到"}), 404
    except Exception as e:
        print(f"[DEBUG] 更新记录时发生错误: {str(e)}")
        if conn:
            conn.rollback()
            conn.close()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass

@app.route('/api/record/<int:record_id>', methods=['GET'])
def get_record(record_id):
    """获取单个入库记录的详细信息"""
    try:
        conn = get_db()
        cursor = conn.cursor(); cursor.execute(convert_query_placeholders("SELECT * FROM inbound_records WHERE id=?"), (record_id,))
        record = cursor.fetchone()
        
        if record:
            # 获取列名
            column_names = [description[0] for description in cursor.description]
            # 创建记录字典
            record_dict = dict(zip(column_names, record))
            conn.close()
            return jsonify(record_dict)
        else:
            conn.close()
            return jsonify({"error": "记录未找到"}), 404
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/api/record/<int:record_id>', methods=['DELETE'])
def delete_record(record_id):
    conn = None
    try:
        conn = get_db()
        
        # 获取删除前的数据
        old_record_cur = conn.cursor(); old_record_cur.execute("SELECT * FROM inbound_records WHERE id=?", (record_id,))
        old_record = old_record_cur.fetchone()
        
        cursor = conn.cursor(); cursor.execute(convert_query_placeholders("DELETE FROM inbound_records WHERE id=?"), (record_id,))
        
        # 如果记录被成功删除，记录日志
        if cursor.rowcount > 0:
            # 记录操作日志
            column_names = [description[0] for description in old_record_cur.description]
            old_data = dict(zip(column_names, old_record)) if old_record else {}
            
            # 删除游标对象，避免序列化错误
            if 'cursor' in old_data:
                del old_data['cursor']
            
            conn.cursor().execute("""INSERT INTO operation_logs 
                (operation_type, table_name, record_id, old_data, new_data)
                VALUES (?, ?, ?, ?, ?)""",
                ('delete', 'inbound_records', record_id, 
                 json.dumps(old_data, default=str), 
                 json.dumps({})))  # 删除操作没有新数据
            
            conn.commit()
            if conn:
                conn.close()
            return jsonify({"success": True})
        else:
            conn.commit()
            if conn:
                conn.close()
            return jsonify({"success": False, "error": "记录未找到"}), 404
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass

@app.route('/api/list')
def list_data():
    print("[DEBUG] /api/list 路由被调用")
    print("[DEBUG] 函数开始执行")
    conn=get_db()
    print(f"[DEBUG] 数据库连接成功: {DB_PATH}")
    
    # 获取当前日期和昨天日期
    current_date = datetime.now().date()
    yesterday_date = current_date - timedelta(days=1)
    print(f"[DEBUG] 当前系统日期: {current_date}")
    print(f"[DEBUG] 昨天日期: {yesterday_date}")

    # 计算当天和昨天的查询时间范围
    # 当天00:00:00
    today_start = datetime.combine(current_date, datetime.min.time())
    # 今天23:59:59
    today_end = datetime.combine(current_date, datetime.max.time())
    # 昨天00:00:00
    yesterday_start = datetime.combine(yesterday_date, datetime.min.time())
    # 昨天23:59:59
    yesterday_end = datetime.combine(yesterday_date, datetime.max.time())
    
    # 次日00:00:00的时间（系统时间，用于上限）
    next_day_start = datetime.combine(current_date + timedelta(days=1), datetime.min.time())

    print(f"[DEBUG] 查询时间范围: {yesterday_start} 到 {next_day_start}")

    # 查询当天和昨天的所有记录
    # 修改：排除车牌号包含'G'的53英尺车辆
    cur = conn.cursor(); cur.execute("""
        SELECT ir.id, ir.dock_no, ir.vehicle_type, ir.vehicle_no, ir.unit, ir.load_amount,
               ir.pieces, ir.time_slot, ir.shift_type, ir.remark, ir.created_at, ir.created_by,
               u.username as created_by_username, ir.duration
        FROM inbound_records ir
        LEFT JOIN users u ON ir.created_by = u.id
        WHERE 
            (ir.created_at >= ? AND ir.created_at <= ?) OR (ir.created_at >= ? AND ir.created_at <= ?)
        ORDER BY ir.created_at DESC""", (
            yesterday_start.strftime('%Y-%m-%d %H:%M:%S'),
            yesterday_end.strftime('%Y-%m-%d %H:%M:%S'),
            today_start.strftime('%Y-%m-%d %H:%M:%S'),
            today_end.strftime('%Y-%m-%d %H:%M:%S')
        ))
    
    raw_rows = cur.fetchall()
    print(f"[DEBUG] 数据库查询返回记录数: {len(raw_rows)}")
    
    rows=[{
        "id":r[0], "dock_no":r[1], "vehicle_type":r[2], "vehicle_no":r[3],
        "unit":r[4], "load_amount":r[5], "pieces":r[6],
        "time_slot":r[7], "shift_type":r[8], "remark":r[9],
        "created_at":r[10],  # 数据库中存储的是系统时间，直接返回
        "created_by":r[11],  # 创建者用户ID
        "created_by_username":r[12] or "未知用户",  # 创建者用户名
        "duration":r[13]  # 时长(分钟)
    } for r in raw_rows]
    
    print(f"[DEBUG] 处理后返回记录数: {len(rows)}")
    conn.close()
    print(f"[DEBUG] 返回JSON数据: {jsonify(rows)}")
    return jsonify(rows)

# 新增API：获取按时间段分组的入库数据

@app.route('/api/inbound_hourly')
def inbound_hourly_data():
    # 获取日期参数，默认为今天
    date_str = request.args.get('date')
    
    conn=get_db()
    
    # 获取洛杉矶当前日期
    la_tz = pytz.timezone('America/Los_Angeles')
    
    if date_str:
        # 如果提供了日期参数，使用指定日期
        try:
            request_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            conn.close()
            return jsonify({"error": "日期格式无效，请使用YYYY-MM-DD格式"}), 400
    else:
        # 如果没有提供日期参数，使用今天
        request_date = datetime.now(la_tz).date()
    
    # 计算次日日期
    next_date = request_date + timedelta(days=1)
    
    # 构建日期范围查询条件（使用洛杉矶时区时间进行计算）
    # 当天05:00:00的时间（洛杉矶时间）
    request_date_5am_la = la_tz.localize(datetime.combine(request_date, datetime.min.time().replace(hour=5)))
    
    # 次日05:00:00的时间（洛杉矶时间，用于上限）
    next_date_5am_la = la_tz.localize(datetime.combine(next_date, datetime.min.time().replace(hour=5)))
    
    # 转换为系统本地时间用于数据库查询
    # 注意：数据库中存储的是系统本地时间，不是UTC时间
    request_date_5am_local = request_date_5am_la.astimezone()
    next_date_5am_local = next_date_5am_la.astimezone()
    
    # 查询入库记录，按时间段分组（查询当天05:00之后到次日05:00之前的所有记录）
    # 同时查询26英尺和53英尺车辆的装载量
    cur = conn.cursor(); cur.execute("""
        SELECT 
            ir.time_slot, 
            SUM(ir.pieces) as total_pieces,
            SUM(CASE 
                WHEN ir.vehicle_type IN ('26英尺', '53英尺') THEN ir.load_amount 
                ELSE 0 
            END) as total_load_amount
        FROM inbound_records ir
        WHERE 
            ir.created_at >= ? AND ir.created_at < ? AND ir.time_slot IS NOT NULL
        GROUP BY ir.time_slot
        ORDER BY ir.time_slot""", (
            request_date_5am_local.strftime('%Y-%m-%d %H:%M:%S'), 
            next_date_5am_local.strftime('%Y-%m-%d %H:%M:%S')
        ))
    rows=[{
        "time_slot": r[0],
        "total_pieces": r[1] if r[1] else 0,
        "total_load_amount": r[2] if r[2] else 0
    } for r in cur.fetchall()]
    return jsonify(rows)

@app.route('/api/pallet_hourly')
def pallet_hourly_data():
    # 获取日期参数，默认为今天
    date_str = request.args.get('date')
    
    conn=get_db()
    
    # 获取洛杉矶当前日期
    la_tz = pytz.timezone('America/Los_Angeles')
    
    if date_str:
        # 如果提供了日期参数，使用指定日期
        try:
            request_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            conn.close()
            return jsonify({"error": "日期格式无效，请使用YYYY-MM-DD格式"}), 400
    else:
        # 如果没有提供日期参数，使用今天
        # 但为了确保能看到最新数据，我们需要调整日期范围
        # 如果当前时间在洛杉矶时间05:00之前，我们应该查看昨天的数据
        now_la = datetime.now(la_tz)
        if now_la.hour < 5:
            # 如果当前洛杉矶时间在05:00之前，使用昨天的日期
            request_date = now_la.date() - timedelta(days=1)
        else:
            # 否则使用今天的日期
            request_date = now_la.date()
    
    # 计算次日日期
    next_date = request_date + timedelta(days=1)
    
    # 构建日期范围查询条件（使用洛杉矶时区时间进行计算）
    # 当天05:00:00的时间（洛杉矶时间）
    request_date_5am_la = la_tz.localize(datetime.combine(request_date, datetime.min.time().replace(hour=5)))
    
    # 次日05:00:00的时间（洛杉矶时间，用于上限）
    next_date_5am_la = la_tz.localize(datetime.combine(next_date, datetime.min.time().replace(hour=5)))
    
    # 转换为系统本地时间用于数据库查询
    # 注意：数据库中存储的是系统本地时间，不是UTC时间
    request_date_5am_local = request_date_5am_la.astimezone()
    next_date_5am_local = next_date_5am_la.astimezone()
    
    # 查询当天数据：入库记录中车辆类型为26英尺或53英尺的记录，按时间段分组
    cur = conn.cursor(); cur.execute("""
        SELECT time_slot, SUM(load_amount) as total_load_amount, COUNT(*) as count
        FROM inbound_records 
        WHERE 
            created_at >= ? AND created_at < ? AND (vehicle_type = '26英尺' OR vehicle_type = '53英尺')
        GROUP BY time_slot
        ORDER BY time_slot""", (
            request_date_5am_local.strftime('%Y-%m-%d %H:%M:%S'), 
            next_date_5am_local.strftime('%Y-%m-%d %H:%M:%S')
        ))
    current_day_rows=[{
        "time_slot": r[0] if r[0] else '未指定',
        "total_load_amount": r[1] if r[1] else 0,
        "count": r[2] if r[2] else 0
    } for r in cur.fetchall()]
    
    # 查询历史数据：所有历史数据按时段分组
    historical_cur = conn.cursor(); historical_cur.execute("""
        SELECT 
            time_slot,
            SUM(load_amount) as total_load_amount,
            COUNT(*) as total_count,
            COUNT(DISTINCT DATE(created_at)) as days_count
        FROM inbound_records
        WHERE vehicle_type IN ('26英尺', '53英尺')
            AND time_slot IS NOT NULL
            AND time_slot != ''
        GROUP BY time_slot
        ORDER BY CAST(time_slot AS INTEGER)
    """)
    
    # 计算每天平均值：总和 ÷ 天数
    historical_avg_rows = []
    for r in historical_cur.fetchall():
        time_slot = r[0]
        total_load = r[1] if r[1] else 0
        days_count = r[3] if r[3] else 1  # 避免除以0
        avg_per_day = round(total_load / days_count, 2) if days_count > 0 else 0
        
        historical_avg_rows.append({
            "time_slot": time_slot,
            "avg_load_amount": avg_per_day,
            "total_load_amount": int(total_load),
            "total_count": r[2] if r[2] else 0,
            "days_count": days_count
        })
    
    conn.close()
    
    # 返回包含当天数据和历史平均值的结构
    return jsonify({
        'current_day': current_day_rows,
        'historical_avg': historical_avg_rows
    })



# 新增API：获取按时间段分组的分拣数据
@app.route('/api/sorting_hourly')
def sorting_hourly_data():
    # 获取日期参数，默认为今天
    date_str = request.args.get('date')
    
    conn=get_db()
    
    if date_str:
        # 如果提供了日期参数，使用指定日期
        try:
            request_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            conn.close()
            return jsonify({"error": "日期格式无效，请使用YYYY-MM-DD格式"}), 400
    else:
        # 如果没有提供日期参数，使用系统当前日期
        request_date = datetime.now().date()
    
    # 计算次日日期
    next_date = request_date + timedelta(days=1)
    
    # 构建日期范围查询条件（使用自然日）
    # 当天00:00:00的时间（系统时间）
    today_start = datetime.combine(request_date, datetime.min.time())
    
    # 次日00:00:00的时间（系统时间，用于上限）
    next_day_start = datetime.combine(next_date, datetime.min.time())
    
    # 查询分拣记录，按时间段分组（按照分拣日期逻辑查询，查询当天00:00之后到次日00:00之前的所有记录）
    cur = conn.cursor(); cur.execute("""SELECT time_slot, SUM(pieces) as total_pieces
                        FROM sorting_records 
                        WHERE 
                            sorting_time >= ? AND sorting_time < ? AND time_slot IS NOT NULL
                        GROUP BY time_slot
                        ORDER BY time_slot""", (
                            today_start.strftime('%Y-%m-%d'), 
                            next_day_start.strftime('%Y-%m-%d')
                        ))
    rows=[{
        "time_slot": r[0],
        "total_pieces": r[1] if r[1] else 0
    } for r in cur.fetchall()]
    return jsonify(rows)

@app.route('/api/history')
def get_history():
    date_str = request.args.get('date')
    
    if not date_str:
        return jsonify({"error": "请提供日期参数"}), 400
    
    conn = get_db()
    
    try:
        # 解析请求的日期
        request_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # 获取洛杉矶当前日期
        la_tz = pytz.timezone('America/Los_Angeles')
        la_today = datetime.now(la_tz).date()
        
        # 检查是否选择了未来日期（明天或以后）
        if request_date > la_today:
            conn.close()
            return jsonify({
                "error": "不能查询未来日期的数据",
                "records": [],
                "sorting_records": [],
                "stats": {
                    "total_vehicles": 0,
                    "total_pieces": 0,
                    "record_count": 0,
                    "vehicle_stats": []
                }
            }), 400
        
        # 计算次日日期
        next_date = request_date + timedelta(days=1)
        
        # 构建日期范围查询条件（使用自然日）
        # 当天00:00:00的时间（系统时间）
        today_start = datetime.combine(request_date, datetime.min.time())
        
        # 次日00:00:00的时间（系统时间，用于上限）
        next_day_start = datetime.combine(next_date, datetime.min.time())
        
        # 查询指定日期的入库记录（查询当天00:00之后到次日00:00之前的所有记录）
        inbound_query = """
            SELECT id, dock_no, vehicle_type, vehicle_no, unit, load_amount,
                   pieces, time_slot, shift_type, remark, created_at, duration
            FROM inbound_records 
            WHERE 
                created_at >= ? AND created_at < ?
            ORDER BY created_at DESC
        """
        inbound_cur = conn.cursor(); inbound_cur.execute(inbound_query, (
            today_start.strftime('%Y-%m-%d %H:%M:%S'), 
            next_day_start.strftime('%Y-%m-%d %H:%M:%S')
        ))
        inbound_rows = [{
            "id": r[0], "dock_no": r[1], "vehicle_type": r[2], "vehicle_no": r[3],
            "unit": r[4], "load_amount": r[5], "pieces": r[6],
            "time_slot": r[7], "shift_type": r[8], "remark": r[9],
            "created_at": r[10],  # 数据库中存储的是系统时间，直接返回
            "duration": r[11]  # 时长(分钟)
        } for r in inbound_cur.fetchall()]
        
        # 查询指定日期的分拣记录（按照分拣日期逻辑查询，查询当天00:00之后到次日00:00之前的所有记录）
        sorting_query = """
            SELECT id, sorting_time, pieces, remark, created_at, time_slot
            FROM sorting_records 
            WHERE 
                sorting_time >= ? AND sorting_time < ?
            ORDER BY created_at DESC
        """
        sorting_cur = conn.cursor(); sorting_cur.execute(sorting_query, (
            today_start.strftime('%Y-%m-%d'), 
            next_day_start.strftime('%Y-%m-%d')
        ))
        sorting_rows = [{
            "id": r[0], "sorting_time": r[1], "pieces": r[2], "remark": r[3],
            "created_at": r[4], "time_slot": r[5]
        } for r in sorting_cur.fetchall()]
        
        # 计算统计信息
        total_vehicles = len(inbound_rows)
        total_pieces = sum((record.get("pieces") or 0) for record in inbound_rows)
        record_count = len(inbound_rows) + len(sorting_rows)
        
        # 各车型统计
        vehicle_stats = {}
        for record in inbound_rows:
            vehicle_type = record.get("vehicle_type", "未知")
            if vehicle_type not in vehicle_stats:
                vehicle_stats[vehicle_type] = {"count": 0, "pieces": 0}
            vehicle_stats[vehicle_type]["count"] += 1
            vehicle_stats[vehicle_type]["pieces"] += (record.get("pieces") or 0)
        
        # 转换为列表格式
        vehicle_stats_list = [
            {
                "vehicle_type": vt,
                "count": stats["count"],
                "total_pieces": stats["pieces"]
            }
            for vt, stats in vehicle_stats.items()
        ]
        
        conn.close()
        
        return jsonify({
            "records": inbound_rows,
            "sorting_records": sorting_rows,
            "stats": {
                "total_vehicles": total_vehicles,
                "total_pieces": total_pieces,
                "record_count": record_count,
                "vehicle_stats": vehicle_stats_list
            }
        })
    except Exception as e:
        conn.close()
        return jsonify({"error": f"处理历史记录查询时出错: {str(e)}"}), 500

@app.route('/api/logs')
def get_operation_logs():
    """获取操作日志列表"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # 查询所有操作日志，按时间倒序排列
        cursor.execute("""
            SELECT id, operation_type, table_name, record_id, old_data, new_data, created_at 
            FROM operation_logs 
            ORDER BY created_at DESC
        """)
        
        logs = cursor.fetchall()
        result = []
        
        for log in logs:
            log_id, operation_type, table_name, record_id, old_data, new_data, created_at = log
            
            # 解析JSON数据
            try:
                old_data_parsed = json.loads(old_data) if old_data else {}
            except:
                old_data_parsed = {"raw_data": old_data}
                
            try:
                new_data_parsed = json.loads(new_data) if new_data else {}
            except:
                new_data_parsed = {"raw_data": new_data}
            
            result.append({
                "id": log_id,
                "operation_type": operation_type,
                "table_name": table_name,
                "record_id": record_id,
                "old_data": old_data_parsed,
                "new_data": new_data_parsed,
                "created_at": created_at
            })
        
        conn.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/logs/<int:log_id>')
def get_operation_log_detail(log_id):
    """获取单个操作日志详情"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # 查询指定ID的操作日志
        cursor.execute("""
            SELECT id, operation_type, table_name, record_id, old_data, new_data, created_at 
            FROM operation_logs 
            WHERE id = ?
        """, (log_id,))
        
        log = cursor.fetchone()
        if not log:
            conn.close()
            return jsonify({"error": "日志未找到"}), 404
        
        log_id, operation_type, table_name, record_id, old_data, new_data, created_at = log
        
        # 解析JSON数据
        try:
            old_data_parsed = json.loads(old_data) if old_data else {}
        except:
            old_data_parsed = {"raw_data": old_data}
            
        try:
            new_data_parsed = json.loads(new_data) if new_data else {}
        except:
            new_data_parsed = {"raw_data": new_data}
        
        result = {
            "id": log_id,
            "operation_type": operation_type,
            "table_name": table_name,
            "record_id": record_id,
            "old_data": old_data_parsed,
            "new_data": new_data_parsed,
            "created_at": created_at
        }
        
        conn.close()
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/sorting', methods=['POST'])
def add_sorting_record():
    data = request.json
    
    conn=get_db()
    
    # 获取当前洛杉矶时间
    la_tz = pytz.timezone('America/Los_Angeles')
    current_la_time = datetime.now(la_tz)
    current_la_time_str = current_la_time.strftime('%Y-%m-%d %H:%M:%S')
    
    conn.cursor().execute("""INSERT INTO sorting_records
        (sorting_time, pieces, remark, time_slot, created_at)
        VALUES (?, ?, ?, ?, ?)""",
        (data.get("sorting_time"), data.get("pieces"), data.get("remark"), data.get("time_slot"), current_la_time_str))
    conn.commit()
    conn.close()
    return jsonify({"success":True})

@app.route('/api/sorting', methods=['GET'])
def get_sorting_records():
    conn=get_db()
    cur = conn.cursor(); cur.execute("""SELECT id, sorting_time, pieces, remark, created_at, time_slot
                        FROM sorting_records ORDER BY created_at DESC""")
    rows=[{
        "id":r[0], "sorting_time":r[1], "pieces":r[2], "remark":r[3],
        "created_at":convert_utc_to_la(r[4]), "time_slot":r[5]
    } for r in cur.fetchall()]
    return jsonify(rows)

@app.route('/api/sorting/<int:record_id>', methods=['DELETE'])
def delete_sorting_record(record_id):
    conn = None
    try:
        conn = get_db()
        
        # 获取删除前的数据
        old_record_cur = conn.cursor(); old_record_cur.execute("SELECT * FROM sorting_records WHERE id=?", (record_id,))
        old_record = old_record_cur.fetchone()
        
        cursor = conn.cursor(); cursor.execute(convert_query_placeholders("DELETE FROM sorting_records WHERE id=?"), (record_id,))
        
        # 如果记录被成功删除，记录日志
        if cursor.rowcount > 0:
            # 记录操作日志
            column_names = [description[0] for description in old_record_cur.description]
            old_data = dict(zip(column_names, old_record)) if old_record else {}
            
            # 删除游标对象，避免序列化错误
            old_data.pop('cursor', None)
            
            conn.cursor().execute("""INSERT INTO operation_logs 
                (operation_type, table_name, record_id, old_data, new_data)
                VALUES (?, ?, ?, ?, ?)""",
                ('delete', 'sorting_records', record_id, 
                 json.dumps(old_data, default=str), 
                 json.dumps({})))  # 删除操作没有新数据
        
            conn.commit()
            conn.close()
            return jsonify({"success": True})
        else:
            conn.commit()
            conn.close()
            return jsonify({"success": False, "error": "记录未找到"}), 404
    except Exception as e:
        if conn:
            conn.rollback()
            conn.close()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass

# 获取揽收预估与实际入库对比数据
@app.route('/api/forecast_vs_actual')
def forecast_vs_actual():
    conn = get_db()
    
    # 查询所有有预估数据的日期，按日期升序排列
    forecast_dates_cur = conn.cursor(); forecast_dates_cur.execute("""
        SELECT forecast_date, forecast_amount 
        FROM pickup_forecast 
        ORDER BY forecast_date ASC
    """)
    
    forecast_records = forecast_dates_cur.fetchall()
    
    dates = []
    forecast_data = []
    actual_data = []
    difference_percent = []
    
    # 遍历所有有预估数据的日期
    for record in forecast_records:
        date_str = record[0]
        forecast_val = record[1]
        
        dates.append(date_str)
        forecast_data.append(forecast_val)
        
        # 查询该日期的实际入库数据
        try:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            day_start = datetime.combine(date, datetime.min.time())
            next_day = date + timedelta(days=1)
            day_end = datetime.combine(next_day, datetime.min.time())
            
            actual_cur = conn.cursor(); actual_cur.execute("""
                SELECT SUM(CASE 
                    WHEN vehicle_type = '53英尺' AND vehicle_no = 'G' THEN 0 
                    ELSE pieces 
                END) as total_pieces
                FROM inbound_records
                WHERE created_at >= ? AND created_at < ?
            """, (day_start.strftime('%Y-%m-%d %H:%M:%S'), 
                  day_end.strftime('%Y-%m-%d %H:%M:%S')))
            
            actual_row = actual_cur.fetchone()
            actual_val = int(actual_row[0]) if actual_row and actual_row[0] else 0
            actual_data.append(actual_val)
            
            # 计算差异百分比
            if forecast_val > 0:
                diff_pct = round((actual_val - forecast_val) / forecast_val * 100, 1)
            else:
                diff_pct = 0
            difference_percent.append(diff_pct)
        except Exception as e:
            print(f"处理日期 {date_str} 时出错: {e}")
            actual_data.append(0)
            difference_percent.append(0)
    
    conn.close()
    
    return jsonify({
        "dates": dates,
        "forecast": forecast_data,
        "actual": actual_data,
        "difference_percent": difference_percent
    })

@app.route('/api/stats')
def get_statistics():
    # 获取日期参数，默认为今天
    date_str = request.args.get('date')
    
    conn=get_db()
    
    # 获取系统当前日期（改为使用系统时间而不是洛杉矶时间）
    if date_str:
        # 如果提供了日期参数，使用指定日期
        try:
            request_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            conn.close()
            return jsonify({"error": "日期格式无效，请使用YYYY-MM-DD格式"}), 400
    else:
        # 如果没有提供日期参数，使用系统当前日期（修改这里）
        request_date = datetime.now().date()
    
    # 计算次日日期
    next_date = request_date + timedelta(days=1)
    
    # 构建日期范围查询条件（使用自然日而不是洛杉矶时区时间）
    # 当天00:00:00的时间（系统时间）
    today_start = datetime.combine(request_date, datetime.min.time())
    
    # 次日00:00:00的时间（系统时间，用于上限）
    next_day_start = datetime.combine(next_date, datetime.min.time())
    
    # 查询属于指定自然日的记录（查询当天00:00之后到次日00:00之前的所有记录）
    records_query = """
        SELECT id, created_at, vehicle_type, time_slot FROM inbound_records 
        WHERE 
            created_at >= ? AND created_at < ?
    """
    records_cur = conn.cursor(); records_cur.execute(records_query, (
        today_start.strftime('%Y-%m-%d %H:%M:%S'), 
        next_day_start.strftime('%Y-%m-%d %H:%M:%S')
    ))
    records = records_cur.fetchall()
    
    # 总车次和总货物量（查询当天00:00之后到次日00:00之前的所有记录）
    # 特殊规则: 53英尺车牌号为G的车辆,货量不计入总计,但车次计入
    total_query = """
        SELECT COUNT(*) as total_vehicles, 
               SUM(CASE 
                   WHEN vehicle_type = '53英尺' AND vehicle_no = 'G' THEN 0 
                   ELSE pieces 
               END) as total_pieces 
        FROM inbound_records 
        WHERE 
            created_at >= ? AND created_at < ?
    """
    total_cur = conn.cursor(); total_cur.execute(total_query, (
        today_start.strftime('%Y-%m-%d %H:%M:%S'), 
        next_day_start.strftime('%Y-%m-%d %H:%M:%S')
    ))
    total_result = total_cur.fetchone()
    total_vehicles = (total_result['total_vehicles'] if USE_POSTGRES else total_result[0]) if total_result else 0
    # 注意: SQLite 中 SUM 可能返回 None, PostgreSQL 也可能
    total_pieces_val = total_result['total_pieces'] if USE_POSTGRES else total_result[1]
    total_pieces = int(total_pieces_val) if total_pieces_val else 0
    
    # 托盘总数（查询当天00:00之后到次日00:00之前，车辆类型为26英尺或53英尺的装载量总和）
    # 特殊规则: 53英尺车牌号为G的车辆,装载量不计入
    pallet_query = """
        SELECT SUM(load_amount) as total_pallets
        FROM inbound_records 
        WHERE 
            created_at >= ? AND created_at < ? 
            AND (vehicle_type = '26英尺' OR vehicle_type = '53英尺')
            AND NOT (vehicle_type = '53英尺' AND vehicle_no = 'G')
    """
    pallet_cur = conn.cursor(); pallet_cur.execute(pallet_query, (
        today_start.strftime('%Y-%m-%d %H:%M:%S'), 
        next_day_start.strftime('%Y-%m-%d %H:%M:%S')
    ))
    pallet_result = pallet_cur.fetchone()
    pallet_val = pallet_result['total_pallets'] if USE_POSTGRES else pallet_result[0]
    total_pallets = int(pallet_val) if pallet_val else 0
    
    # 各车型统计（查询当天00:00之后到次日00:00之前的所有记录）
    # 特殊规则: 53英尺车牌号为G的车辆,车次计入但货量不计入
    vehicle_stats_query = """
        SELECT vehicle_type, 
               COUNT(*) as count, 
               SUM(CASE 
                   WHEN vehicle_type = '53英尺' AND vehicle_no = 'G' THEN 0 
                   ELSE pieces 
               END) as total_pieces 
        FROM inbound_records 
        WHERE 
            created_at >= ? AND created_at < ?
        GROUP BY vehicle_type
    """
    vehicle_stats_cur = conn.cursor(); vehicle_stats_cur.execute(vehicle_stats_query, (
        today_start.strftime('%Y-%m-%d %H:%M:%S'), 
        next_day_start.strftime('%Y-%m-%d %H:%M:%S')
    ))
    vehicle_stats = [{
        "vehicle_type": r[0],
        "count": r[1],
        "total_pieces": int(r[2]) if r[2] else 0
    } for r in vehicle_stats_cur.fetchall()]
    
    # 初始化统计变量
    vehicles_19_to_20 = 0
    # 统计19:00-20:00时间段各车型到车数量
    vehicles_19_to_20_by_type = {}
    
    # 统计20:00-21:00时间段记录
    vehicles_20_to_21 = 0
    # 统计20:00-21:00时间段各车型到车数量
    vehicles_20_to_21_by_type = {}
    
    # 统计超过24:00的记录（即次日00:00之后的记录）
    vehicles_after_24 = 0
    
    # 处理每条记录，用于统计特定时间段的数据（按录入的时间段time_slot统计）
    for record in records:
        record_id, created_at_str, vehicle_type, time_slot = record
        # 基于录入的时间段进行统计
        if time_slot:
            try:
                time_slot_int = int(time_slot)
                # 检查是否在19:00-20:00之间（录入的时间段为19）
                if time_slot_int == 19:
                    vehicles_19_to_20 += 1
                    
                    # 统计19:00-20:00时间段各车型到车数量
                    if vehicle_type not in vehicles_19_to_20_by_type:
                        vehicles_19_to_20_by_type[vehicle_type] = 0
                    vehicles_19_to_20_by_type[vehicle_type] += 1
                
                # 检查是否在20:00-21:00之间（录入的时间段为20）
                if time_slot_int == 20:
                    vehicles_20_to_21 += 1
                    
                    # 统计20:00-21:00时间段各车型到车数量
                    if vehicle_type not in vehicles_20_to_21_by_type:
                        vehicles_20_to_21_by_type[vehicle_type] = 0
                    vehicles_20_to_21_by_type[vehicle_type] += 1
                
                # 检查是否是超过24:00的记录（录入的时间段为24或更大）
                if time_slot_int >= 24:
                    vehicles_after_24 += 1
            except ValueError:
                # 如果time_slot不是有效的整数，跳过这条记录
                pass
        else:
            # 如果没有录入时间段，仍然使用原来基于创建时间的逻辑作为后备
            if created_at_str:
                try:
                    # 将UTC时间字符串转换为datetime对象
                    utc_time = datetime.strptime(created_at_str, '%Y-%m-%d %H:%M:%S')
                    utc_time = pytz.utc.localize(utc_time)
                    # 转换为系统本地时间（修改这里）
                    local_time = utc_time.astimezone()
                    
                    # 检查是否在19:00-20:00之间（系统本地时间）
                    if local_time.hour == 19:
                        vehicles_19_to_20 += 1
                        
                        # 统计19:00-20:00时间段各车型到车数量
                        if vehicle_type not in vehicles_19_to_20_by_type:
                            vehicles_19_to_20_by_type[vehicle_type] = 0
                        vehicles_19_to_20_by_type[vehicle_type] += 1
                    
                    # 检查是否在20:00-21:00之间（系统本地时间）
                    if local_time.hour == 20:
                        vehicles_20_to_21 += 1
                        
                        # 统计20:00-21:00时间段各车型到车数量
                        if vehicle_type not in vehicles_20_to_21_by_type:
                            vehicles_20_to_21_by_type[vehicle_type] = 0
                        vehicles_20_to_21_by_type[vehicle_type] += 1
                    
                    # 检查是否是明天的记录（即次日00:00之后的记录）
                    if local_time.date() > request_date:
                        vehicles_after_24 += 1
                except Exception as e:
                    print(f"处理记录 {record_id} 的时间时出错: {e}")
    
    conn.close()
    
    return jsonify({
        "total_vehicles": total_vehicles,
        "total_pieces": total_pieces,
        "total_pallets": total_pallets,
        "vehicle_stats": vehicle_stats,
        "vehicles_19_to_20": vehicles_19_to_20,
        "vehicles_19_to_20_by_type": vehicles_19_to_20_by_type,
        "vehicles_20_to_21": vehicles_20_to_21,
        "vehicles_20_to_21_by_type": vehicles_20_to_21_by_type,
        "vehicles_after_24": vehicles_after_24
    })

@app.route('/api/daily_trend')
def get_daily_trend():
    """获取每日货物趋势数据（显示所有有记录的日期）"""
    try:
        conn = get_db()
        
        # 查询数据库中所有有记录的日期（按日期分组）
        # 使用DATE函数提取日期部分
        dates_query = """
            SELECT DISTINCT DATE(created_at) as record_date
            FROM inbound_records
            ORDER BY record_date ASC
        """
        cursor = conn.cursor(); cursor.execute(dates_query)
        record_dates = [row[0] for row in cursor.fetchall()]
        
        # 如果没有记录，返回空数组
        if not record_dates:
            conn.close()
            return jsonify([])
        
        # 美国联邦假期（2025-2026年）
        US_FEDERAL_HOLIDAYS = {
            # 2025
            '2025-01-01': "New Year's Day",
            '2025-01-20': "Martin Luther King Jr. Day",
            '2025-02-17': "Presidents' Day",
            '2025-05-26': "Memorial Day",
            '2025-07-04': "Independence Day",
            '2025-09-01': "Labor Day",
            '2025-10-13': "Columbus Day",
            '2025-11-11': "Veterans Day",
            '2025-11-27': "Thanksgiving",
            '2025-12-25': "Christmas Day",
            # 2026
            '2026-01-01': "New Year's Day",
            '2026-01-19': "Martin Luther King Jr. Day",
            '2026-02-16': "Presidents' Day",
            '2026-05-25': "Memorial Day",
            '2026-07-03': "Independence Day (Observed)",
            '2026-07-04': "Independence Day",
            '2026-09-07': "Labor Day",
            '2026-10-12': "Columbus Day",
            '2026-11-11': "Veterans Day",
            '2026-11-26': "Thanksgiving",
            '2026-12-25': "Christmas Day"
        }
        
        # 准备结果数组
        result = []
        
        # 为每个有记录的日期查询数据
        for date_str in record_dates:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            next_date = target_date + timedelta(days=1)
            
            # 构建日期范围查询条件
            day_start = datetime.combine(target_date, datetime.min.time())
            day_end = datetime.combine(next_date, datetime.min.time())
            
            # 查询当天的货物总量、车次总数和托盘总数
            query = """
                SELECT 
                    SUM(pieces) as total_pieces,
                    COUNT(*) as total_vehicles,
                    SUM(CASE 
                        WHEN vehicle_type IN ('26英尺', '53英尺') THEN load_amount 
                        ELSE 0 
                    END) as total_pallets
                FROM inbound_records
                WHERE created_at >= ? AND created_at < ?
            """
            cursor = conn.cursor(); cursor.execute(query, (
                day_start.strftime('%Y-%m-%d %H:%M:%S'),
                day_end.strftime('%Y-%m-%d %H:%M:%S')
            ))
            row = cursor.fetchone()
            # 应用取整规则：千百十个位全部为0
            total_pieces = round_to_ten_thousand(row[0])
            total_vehicles = int(row[1]) if row[1] else 0
            total_pallets = int(row[2]) if row[2] else 0
            
            # 获取星期几 (0=Monday, 6=Sunday)
            weekday = target_date.weekday()
            weekday_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            
            # 检查是否是假期
            is_holiday = date_str in US_FEDERAL_HOLIDAYS
            holiday_name = US_FEDERAL_HOLIDAYS.get(date_str, '')
            
            result.append({
                'date': target_date.strftime('%Y-%m-%d'),
                'weekday': weekday_names[weekday],
                'weekday_num': weekday,  # 0-6
                'is_holiday': is_holiday,
                'holiday_name': holiday_name,
                'total_pieces': total_pieces,
                'total_vehicles': total_vehicles,
                'total_pallets': total_pallets
            })
        
        conn.close()
        return jsonify(result)
    
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': f'获取每日趋势数据出错: {str(e)}'}), 500



@app.route('/api/week_comparison')
def get_week_comparison():
    """获取所有周的对比数据（使用自然周：周一00:00到周日23:59）"""
    try:
        conn = get_db()
        
        # 1. 获取最小日期（第一条记录的时间）
        query = "SELECT MIN(created_at) FROM inbound_records"
        cursor = conn.cursor(); cursor.execute(query)
        min_res = cursor.fetchone()
        min_str = (min_res['min'] if USE_POSTGRES else min_res[0]) if min_res else None
        
        if not min_str:
            conn.close()
            return jsonify([])  # 没有数据
            
        # 解析最小日期
        try:
            min_date = datetime.strptime(min_str.split(' ')[0], '%Y-%m-%d').date()
        except Exception:
            # 如果解析失败，回退到当前日期（不应该发生）
            min_date = datetime.now().date()
            
        # 设置最大日期为今天（确保显示到本周）
        max_date = datetime.now().date()
        
        # 辅助函数：获取自然周的起止日期
        def get_natural_week_range(date):
            """获取自然周的起止时间（周一到周日）"""
            # weekday() 返回0-6，0是周一
            weekday = date.weekday()
            week_start = date - timedelta(days=weekday)
            week_end = week_start + timedelta(days=6)
            return week_start, week_end
            
        # 对齐最小日期到该周的周一
        current_start, current_end = get_natural_week_range(min_date)
        
        weeks_data = []
        
        # 循环直到包含当前日期
        while current_start <= max_date:
            # 查询该周数据
            week_query = """
                SELECT 
                    COUNT(*) as vehicle_count,
                    SUM(pieces) as total_pieces
                FROM inbound_records
                WHERE created_at >= ? AND created_at <= ?
            """
            
            # 构造完整的日期时间范围 (周一 00:00:00 到 周日 23:59:59.999999)
            week_start_dt = datetime.combine(current_start, datetime.min.time())
            week_end_dt = datetime.combine(current_end, datetime.max.time())
            
            cursor = conn.cursor(); cursor.execute(week_query, (
                week_start_dt.strftime('%Y-%m-%d %H:%M:%S'),
                week_end_dt.strftime('%Y-%m-%d %H:%M:%S')
            ))
            
            row = cursor.fetchone()
            vehicle_count = row[0] if row[0] else 0
            # 应用取整规则：千百十个位全部为0
            total_pieces = round_to_ten_thousand(row[1])
            
            # 计算环比（如果不是第一周）
            pieces_change_percent = 0
            vehicles_change_percent = 0
            
            if weeks_data:
                last_week = weeks_data[-1]
                last_pieces = last_week['total_pieces']
                last_vehicles = last_week['vehicle_count']
                
                if last_pieces > 0:
                    pieces_change_percent = ((total_pieces - last_pieces) / last_pieces) * 100
                else:
                    pieces_change_percent = 100 if total_pieces > 0 else 0
                    
                if last_vehicles > 0:
                    vehicles_change_percent = ((vehicle_count - last_vehicles) / last_vehicles) * 100
                else:
                    vehicles_change_percent = 100 if vehicle_count > 0 else 0
            
            weeks_data.append({
                'start_date': current_start.strftime('%Y-%m-%d'),
                'end_date': current_end.strftime('%Y-%m-%d'),
                'vehicle_count': vehicle_count,
                'total_pieces': total_pieces,
                'pieces_change_percent': round(pieces_change_percent, 2),
                'vehicles_change_percent': round(vehicles_change_percent, 2)
            })
            
            # 移动到下一周
            current_start = current_start + timedelta(days=7)
            current_end = current_end + timedelta(days=7)
            
        conn.close()
        
        return jsonify(weeks_data)
    
    except Exception as e:
        if 'conn' in locals():
            conn.close()
        return jsonify({'error': f'获取周环比数据出错: {str(e)}'}), 500



@app.route('/api/export_csv')
def export_csv():
    try:
        # 获取查询日期参数，如果没有则使用当天
        date_str = request.args.get('date')
        
        if not date_str:
            # 获取系统当前日期（改为使用系统时间而不是洛杉矶时间）
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        conn = get_db()
        
        # 解析请求的日期
        request_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # 计算次日日期
        next_date = request_date + timedelta(days=1)
        
        # 构建日期范围查询条件（使用自然日而不是洛杉矶时区时间）
        # 当天00:00:00的时间（系统时间）
        today_start = datetime.combine(request_date, datetime.min.time())
        
        # 次日00:00:00的时间（系统时间，用于上限）
        next_day_start = datetime.combine(next_date, datetime.min.time())
        
        # 总车次和总货物量（查询当天00:00之后到次日00:00之前的所有记录）
        total_query = """
            SELECT COUNT(*) as total_vehicles, SUM(pieces) as total_pieces 
            FROM inbound_records 
            WHERE 
                created_at >= ? AND created_at < ?
        """
        total_cur = conn.cursor(); total_cur.execute(total_query, (
            today_start.strftime('%Y-%m-%d %H:%M:%S'), 
            next_day_start.strftime('%Y-%m-%d %H:%M:%S')
        ))
        total_result = total_cur.fetchone()
        total_vehicles = total_result[0] if total_result[0] else 0
        total_pieces = int(total_result[1]) if total_result[1] else 0
        
        # 托盘总数（查询当天00:00之后到次日00:00之前，车辆类型为26英尺或53英尺的装载量总和）
        pallet_query = """
            SELECT SUM(load_amount) as total_pallets
            FROM inbound_records 
            WHERE 
                created_at >= ? AND created_at < ? AND (vehicle_type = '26英尺' OR vehicle_type = '53英尺')
        """
        pallet_cur = conn.cursor(); pallet_cur.execute(pallet_query, (
            today_start.strftime('%Y-%m-%d %H:%M:%S'), 
            next_day_start.strftime('%Y-%m-%d %H:%M:%S')
        ))
        pallet_result = pallet_cur.fetchone()
        total_pallets = int(pallet_result[0]) if pallet_result[0] else 0
        
        # 各车型统计（查询当天00:00之后到次日00:00之前的所有记录）
        vehicle_stats_query = """
            SELECT vehicle_type, COUNT(*) as count, SUM(pieces) as total_pieces 
            FROM inbound_records 
            WHERE 
                created_at >= ? AND created_at < ?
            GROUP BY vehicle_type
        """
        vehicle_stats_cur = conn.cursor(); vehicle_stats_cur.execute(vehicle_stats_query, (
            today_start.strftime('%Y-%m-%d %H:%M:%S'), 
            next_day_start.strftime('%Y-%m-%d %H:%M:%S')
        ))
        vehicle_stats = [{
            "vehicle_type": r[0],
            "count": r[1],
            "total_pieces": int(r[2]) if r[2] else 0
        } for r in vehicle_stats_cur.fetchall()]
        
        # 查询属于指定自然日的记录（查询当天00:00之后到次日00:00之前的所有记录）
        records_query = """
            SELECT id, created_at, vehicle_type, time_slot FROM inbound_records 
            WHERE 
                created_at >= ? AND created_at < ?
        """
        records_cur = conn.cursor(); records_cur.execute(records_query, (
            today_start.strftime('%Y-%m-%d %H:%M:%S'), 
            next_day_start.strftime('%Y-%m-%d %H:%M:%S')
        ))
        records = records_cur.fetchall()
        
        # 初始化统计变量
        vehicles_19_to_20 = 0
        vehicles_20_to_21 = 0
        vehicles_after_24 = 0
        
        # 处理每条记录，用于统计特定时间段的数据（按录入的时间段time_slot统计）
        for record in records:
            record_id, created_at_str, vehicle_type, time_slot = record
            # 基于录入的时间段进行统计
            if time_slot:
                try:
                    time_slot_int = int(time_slot)
                    # 检查是否在19:00-20:00之间（录入的时间段为19）
                    if time_slot_int == 19:
                        vehicles_19_to_20 += 1
                    # 检查是否在20:00-21:00之间（录入的时间段为20）
                    if time_slot_int == 20:
                        vehicles_20_to_21 += 1
                    # 检查是否是超过24:00的记录（录入的时间段为24或更大）
                    if time_slot_int >= 24:
                        vehicles_after_24 += 1
                except ValueError:
                    # 如果time_slot不是有效的整数，跳过这条记录
                    pass
            else:
                # 如果没有录入时间段，仍然使用原来基于创建时间的逻辑作为后备
                if created_at_str:
                    try:
                        # 将UTC时间字符串转换为datetime对象
                        utc_time = datetime.strptime(created_at_str, '%Y-%m-%d %H:%M:%S')
                        utc_time = pytz.utc.localize(utc_time)
                        # 转换为系统本地时间（修改这里）
                        local_time = utc_time.astimezone()
                        
                        # 检查是否在19:00-20:00之间（系统本地时间）
                        if local_time.hour == 19:
                            vehicles_19_to_20 += 1
                        # 检查是否在20:00-21:00之间（系统本地时间）
                        if local_time.hour == 20:
                            vehicles_20_to_21 += 1
                        # 检查是否是明天的记录（即次日00:00之后的记录）
                        if local_time.date() > request_date:
                            vehicles_after_24 += 1
                    except Exception as e:
                        print(f"处理记录 {record_id} 的时间时出错: {e}")
        
        conn.close()
        
        # 创建CSV内容
        import csv
        import io
        
        # 创建内存中的CSV文件
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
        
        # 写入BOM以支持UTF-8编码的Excel打开
        output.write('\ufeff')
        
        # 写入统计摘要标题
        writer.writerow(['统计摘要'])
        writer.writerow(['总车次', '总货物量', '托盘总数', '19:00-20:00到车数', '20:00-21:00到车数', '超过24:00到车数'])
        
        # 写入统计摘要数据
        writer.writerow([total_vehicles, total_pieces, total_pallets, vehicles_19_to_20, vehicles_20_to_21, vehicles_after_24])
        
        # 添加空行分隔
        writer.writerow([])
        
        # 写入各车型统计标题
        writer.writerow(['各车型统计'])
        writer.writerow(['车型', '车次', '货物总量'])
        
        # 写入各车型统计数据
        for stat in vehicle_stats:
            writer.writerow([stat["vehicle_type"], stat["count"], stat["total_pieces"]])
        
        # 获取CSV内容
        csv_content = output.getvalue()
        output.close()
        
        # 创建响应对象
        from flask import Response
        filename = f"inbound_stats_summary_{date_str}.csv"  # 使用英文文件名避免编码问题
        
        response = Response(
            csv_content,
            mimetype='text/csv',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
        return response
        
    except Exception as e:
        print(f"导出CSV文件出错: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"导出失败: {str(e)}"}), 500

@app.route('/api/export_excel')
def export_excel():
    try:
        # 获取查询日期参数，如果没有则使用当天
        date_str = request.args.get('date')
        
        if not date_str:
            # 获取系统当前日期（改为使用系统时间而不是洛杉矶时间）
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        conn = get_db()
        
        # 解析请求的日期
        request_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # 计算次日日期
        next_date = request_date + timedelta(days=1)
        
        # 构建日期范围查询条件（使用自然日而不是洛杉矶时区时间）
        # 当天00:00:00的时间（系统时间）
        today_start = datetime.combine(request_date, datetime.min.time())
        
        # 次日00:00:00的时间（系统时间，用于上限）
        next_day_start = datetime.combine(next_date, datetime.min.time())
        
        # 查询指定日期的入库记录（查询当天00:00之后到次日00:00之前的所有记录）
        inbound_query = """
            SELECT id, dock_no, vehicle_type, vehicle_no, unit, load_amount,
                   pieces, time_slot, shift_type, remark, created_at, duration
            FROM inbound_records 
            WHERE 
                created_at >= ? AND created_at < ?
            ORDER BY created_at DESC
        """
        inbound_cur = conn.cursor(); inbound_cur.execute(inbound_query, (
            today_start.strftime('%Y-%m-%d %H:%M:%S'), 
            next_day_start.strftime('%Y-%m-%d %H:%M:%S')
        ))
        inbound_rows = [{
            "id": r[0], "dock_no": r[1], "vehicle_type": r[2], "vehicle_no": r[3],
            "unit": r[4], "load_amount": r[5], "pieces": r[6],
            "time_slot": r[7], "shift_type": r[8], "remark": r[9],
            "created_at": r[10],  # 数据库中存储的是系统时间，直接返回
            "duration": r[11]  # 时长(分钟)
        } for r in inbound_cur.fetchall()]
        
        # 查询指定日期的分拣记录（按照自然日逻辑查询，查询当天00:00之后到次日00:00之前的所有记录）
        sorting_query = """
            SELECT id, sorting_time, pieces, remark, created_at, time_slot
            FROM sorting_records 
            WHERE 
                created_at >= ? AND created_at < ?
            ORDER BY created_at DESC
        """
        sorting_cur = conn.cursor(); sorting_cur.execute(sorting_query, (
            today_start.strftime('%Y-%m-%d %H:%M:%S'), 
            next_day_start.strftime('%Y-%m-%d %H:%M:%S')
        ))
        sorting_rows = [{
            "id": r[0], "sorting_time": r[1], "pieces": r[2], "remark": r[3],
            "created_at": r[4], "time_slot": r[5]
        } for r in sorting_cur.fetchall()]
        
        conn.close()
        
        # 创建Excel工作簿
        wb = Workbook()
        
        # 创建入库记录工作表
        ws1 = wb.active
        ws1.title = "入库记录"
        
        # 添加表头
        inbound_headers = ['ID', '码头号', '车辆类型', '车牌号', '单位', '装载量', '件数', '时间段', '班次类型', '备注', '创建时间', '时长(分钟)']
        ws1.append(inbound_headers)
        
        # 设置表头样式
        header_font = Font(bold=True)
        header_fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
        for col in range(1, len(inbound_headers) + 1):
            cell = ws1.cell(row=1, column=col)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
        
        # 添加入库数据
        for row_dict in inbound_rows:
            # 按照表头顺序构造行数据
            row_data = [
                row_dict["id"], row_dict["dock_no"], row_dict["vehicle_type"], row_dict["vehicle_no"],
                row_dict["unit"], row_dict["load_amount"], row_dict["pieces"],
                row_dict["time_slot"], row_dict["shift_type"], row_dict["remark"], row_dict["created_at"],
                row_dict.get("duration", "")  # 时长(分钟),如果没有则为空
            ]
            ws1.append(row_data)
        
        # 调整列宽
        for column in ws1.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2)
            ws1.column_dimensions[column_letter].width = min(adjusted_width, 50)
        
        # 创建分拣记录工作表（只有在有数据时才创建）
        if sorting_rows:
            ws2 = wb.create_sheet("分拣记录")
            
            # 添加表头
            sorting_headers = ['ID', '分拣日期', '件数', '时间段', '备注', '创建时间']
            ws2.append(sorting_headers)
            
            # 设置表头样式
            for col in range(1, len(sorting_headers) + 1):
                cell = ws2.cell(row=1, column=col)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = Alignment(horizontal="center")
            
            # 添加分拣数据
            for row_dict in sorting_rows:
                # 按照表头顺序构造行数据
                row_data = [
                    row_dict["id"], row_dict["sorting_time"], row_dict["pieces"],
                    row_dict["time_slot"], row_dict["remark"], row_dict["created_at"]
                ]
                ws2.append(row_data)
            
            # 调整列宽
            for column in ws2.columns:
                max_length = 0
                column_letter = get_column_letter(column[0].column)
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = (max_length + 2)
                ws2.column_dimensions[column_letter].width = min(adjusted_width, 50)
        
        # 保存Excel文件
        filename = f"inbound_stats_{date_str}.xlsx"  # 使用英文文件名避免编码问题
        filepath = os.path.join(os.path.dirname(__file__), filename)
        wb.save(filepath)
        
        # 返回Excel文件，使用更直接的方法避免文件名编码问题
        from flask import Response
        import os
        
        # 读取文件内容
        with open(filepath, 'rb') as f:
            file_content = f.read()
        
        # 创建响应对象，明确设置Content-Type和Content-Disposition
        response = Response(
            file_content,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
        return response
        
    except Exception as e:
        print(f"导出Excel文件出错: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"导出失败: {str(e)}"}), 500

# 新增API：导出最近记录
@app.route('/api/export_recent_records')
def export_recent_records():
    try:
        conn = get_db()
        
        # 获取系统当前日期
        today = datetime.now().date()
        
        # 计算次日日期
        next_date = today + timedelta(days=1)
        
        # 构建日期范围查询条件（使用自然日）
        # 当天00:00:00的时间（系统时间）
        today_start = datetime.combine(today, datetime.min.time())
        
        # 次日00:00:00的时间（系统时间，用于上限）
        next_day_start = datetime.combine(next_date, datetime.min.time())
        
        # 查询属于当前自然日的记录（查询当天00:00之后到次日00:00之前的所有记录）
        cur = conn.cursor(); cur.execute("""
            SELECT id, dock_no, vehicle_type, vehicle_no, unit, load_amount,
                   pieces, time_slot, shift_type, remark, created_at
            FROM inbound_records 
            WHERE 
                created_at >= ? AND created_at < ?
            ORDER BY created_at DESC""", (
                today_start.strftime('%Y-%m-%d %H:%M:%S'), 
                next_day_start.strftime('%Y-%m-%d %H:%M:%S')
            ))
        
        rows = [{
            "id": r[0], "dock_no": r[1], "vehicle_type": r[2], "vehicle_no": r[3],
            "unit": r[4], "load_amount": r[5], "pieces": r[6],
            "time_slot": r[7], "shift_type": r[8], "remark": r[9],
            "created_at": r[10]  # 数据库中存储的是系统时间，直接返回
        } for r in cur.fetchall()]
        
        conn.close()
        
        # 创建Excel工作簿
        wb = Workbook()
        
        # 创建工作表
        ws = wb.active
        ws.title = "最近记录"
        
        # 添加表头
        headers = ['ID', '码头号', '车辆类型', '车牌号', '单位', '装载量', '件数', '时间段', '班次类型', '备注', '创建时间']
        ws.append(headers)
        
        # 设置表头样式
        header_font = Font(bold=True)
        header_fill = PatternFill(start_color="CCCCCC", end_color="CCCCCC", fill_type="solid")
        for col in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center")
        
        # 添加数据
        for row_dict in rows:
            # 按照表头顺序构造行数据
            row_data = [
                row_dict["id"], row_dict["dock_no"], row_dict["vehicle_type"], row_dict["vehicle_no"],
                row_dict["unit"], row_dict["load_amount"], row_dict["pieces"],
                row_dict["time_slot"], row_dict["shift_type"], row_dict["remark"], row_dict["created_at"]
            ]
            ws.append(row_data)
        
        # 调整列宽
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2)
            ws.column_dimensions[column_letter].width = min(adjusted_width, 50)
        
        # 保存Excel文件
        filename = f"recent_records_{today.strftime('%Y-%m-%d')}.xlsx"
        filepath = os.path.join(os.path.dirname(__file__), filename)
        wb.save(filepath)
        
        # 返回Excel文件
        from flask import Response
        
        # 读取文件内容
        with open(filepath, 'rb') as f:
            file_content = f.read()
        
        # 创建响应对象，明确设置Content-Type和Content-Disposition
        response = Response(
            file_content,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={
                'Content-Disposition': f'attachment; filename="{filename}"'
            }
        )
        return response
        
    except Exception as e:
        print(f"导出最近记录Excel文件出错: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"导出失败: {str(e)}"}), 500

# 用户登录API
# 权限检查辅助函数
def check_page_permission(page_name):
    """检查用户是否有页面访问权限"""
    if 'user_id' not in session:
        return False
    
    # 管理员有所有权限
    if session.get('role') == 'admin':
        return True
    
    # 查询用户权限
    try:
        conn = get_db()
        cursor = conn.cursor(); cursor.execute("""
            SELECT can_view FROM user_permissions
            WHERE user_id = ? AND page_name = ?
        """, (session['user_id'], page_name))
        
        result = cursor.fetchone()
        conn.close()
        
        return result and bool(result['can_view'] if USE_POSTGRES else result[0])
    except:
        return False

def get_first_accessible_page(user_id, role):
    """获取用户第一个有权限访问的页面"""
    print(f"[DEBUG] get_first_accessible_page called: user_id={user_id}, role={role}")
    
    # 管理员默认跳转到首页
    if role == 'admin':
        print(f"[DEBUG] User is admin, redirecting to /")
        return '/'
    
    # 页面优先级顺序
    page_priority = [
        ('index', '/'),
        ('sorting', '/sorting'),
        ('history', '/history'),
        ('statistics', '/statistics'),
        ('logs', '/logs')
    ]
    
    try:
        conn = get_db()
        for page_name, page_url in page_priority:
            cursor = conn.cursor(); cursor.execute("""
                SELECT can_view FROM user_permissions
                WHERE user_id = ? AND page_name = ? AND can_view = 1
            """, (user_id, page_name))
            
            result = cursor.fetchone()
            print(f"[DEBUG] Checking {page_name}: result={result}")
            
            if result:
                print(f"[DEBUG] Found accessible page: {page_name} -> {page_url}")
                conn.close()
                return page_url
        
        conn.close()
        print(f"[DEBUG] No accessible pages found, redirecting to /no_permission")
    except Exception as e:
        print(f"[DEBUG] Exception in get_first_accessible_page: {e}")
        pass
    
    # 如果没有任何页面权限,跳转到无权限页面
    return '/no_permission'

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400
    
    # 对密码进行哈希处理
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    # 查询用户
    conn = get_db()
    cursor = conn.cursor(); cursor.execute(convert_query_placeholders("""
        SELECT u.id, u.username, u.role, u.is_active
        FROM users u
        WHERE u.username = ? AND u.password_hash = ? AND u.is_active = TRUE
    """), (username, password_hash))
    
    user = cursor.fetchone()
    conn.close()
    
    if user:
        # 登录成功，设置session
        session['user_id'] = user['id'] if USE_POSTGRES else user[0]
        session['username'] = user['username'] if USE_POSTGRES else user[1]
        session['role'] = user['role'] if USE_POSTGRES else user[2]
        
        # 获取第一个有权限的页面
        user_id = user['id'] if USE_POSTGRES else user[0]
        user_role = user['role'] if USE_POSTGRES else user[2]
        redirect_url = get_first_accessible_page(user_id, user_role)
        
        return jsonify({
            'success': True,
            'redirect': redirect_url,
            'user': {
                'id': user['id'] if USE_POSTGRES else user[0],
                'username': user['username'] if USE_POSTGRES else user[1],
                'role': user['role'] if USE_POSTGRES else user[2]
            }
        })
    else:
        return jsonify({'error': '用户名或密码错误'}), 401

# 用户登出API
@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

# 检查用户登录状态
@app.route('/api/check_login')
def check_login():
    if 'user_id' in session:
        return jsonify({
            'logged_in': True,
            'user': {
                'id': session['user_id'],
                'username': session['username'],
                'role': session['role']
            }
        })
    else:
        return jsonify({'logged_in': False})

# 获取用户权限
@app.route('/api/user_permissions')
def get_user_permissions():
    if 'user_id' not in session:
        return jsonify({'error': '未登录'}), 401
    
    user_id = session['user_id']
    
    # 查询用户权限
    conn = get_db()
    cursor = conn.cursor(); cursor.execute("""
        SELECT page_name, can_view, can_edit, can_delete
        FROM user_permissions
        WHERE user_id = ?
    """, (user_id,))
    
    permissions = {}
    for row in cursor.fetchall():
        page_name, can_view, can_edit, can_delete = row
        permissions[page_name] = {
            'can_view': bool(can_view),
            'can_edit': bool(can_edit),
            'can_delete': bool(can_delete)
        }
    
    conn.close()
    return jsonify(permissions)

# 用户权限装饰器
def require_permission(page_name, permission_type='view'):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 检查是否登录
            if 'user_id' not in session:
                return jsonify({'error': '未登录'}), 401
            
            # 检查权限
            conn = get_db()
            query = f"""
                SELECT up.can_{permission_type}
                FROM user_permissions up
                WHERE up.user_id = ? AND up.page_name = ?
            """
            cursor = conn.cursor(); cursor.execute(query, (session['user_id'], page_name))
            result = cursor.fetchone()
            conn.close()
            
            check_val = result[f'can_{permission_type}'] if USE_POSTGRES else result[0]
            if not result or not check_val:
                return jsonify({'error': '权限不足'}), 403
            
            return func(*args, **kwargs)
        return wrapper
    return decorator

# 获取所有用户列表（仅管理员）
@app.route('/api/users')
def get_users():
    if 'user_id' not in session:
        return jsonify({'error': '未登录'}), 401
    
    # 只有管理员可以查看用户列表
    if session.get('role') != 'admin':
        return jsonify({'error': '权限不足'}), 403
    
    conn = get_db()
    cursor = conn.cursor(); cursor.execute("""
        SELECT u.id, u.username, u.role, u.is_active, u.created_at
        FROM users u
        ORDER BY u.created_at DESC
    """)
    
    users = []
    for row in cursor.fetchall():
        users.append({
            'id': row[0],
            'username': row[1],
            'role': row[2],
            'is_active': bool(row[3]),
            'created_at': row[4]
        })
    
    conn.close()
    return jsonify(users)

# 创建新用户（仅管理员）
@app.route('/api/users', methods=['POST'])
def create_user():
    if 'user_id' not in session:
        return jsonify({'error': '未登录'}), 401
    
    # 只有管理员可以创建用户
    if session.get('role') != 'admin':
        return jsonify({'error': '权限不足'}), 403
    
    data = request.json
    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'user')
    is_active = data.get('is_active', True)
    
    if not username or not password:
        return jsonify({'error': '用户名和密码不能为空'}), 400
    
    # 对密码进行哈希处理
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    try:
        conn = get_db()
        cursor = conn.cursor(); cursor.execute("""
            INSERT INTO users (username, password_hash, role, is_active)
            VALUES (?, ?, ?, ?)
        """, (username, password_hash, role, is_active))
        
        user_id = cursor.lastrowid
        conn.commit()
        
        # 为新用户设置默认权限（无权限）
        pages = ['index', 'sorting', 'history', 'statistics', 'logs']
        for page in pages:
            conn.cursor().execute("""
                INSERT INTO user_permissions (user_id, page_name, can_view, can_edit, can_delete)
                VALUES (?, ?, 0, 0, 0)
            """, (user_id, page))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'user_id': user_id})
    except sqlite3.IntegrityError:
        return jsonify({'error': '用户名已存在'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 用户权限管理(仅管理员) - GET获取权限, PUT更新权限
@app.route('/api/users/<int:user_id>/permissions', methods=['GET', 'PUT'])
def manage_user_permissions(user_id):
    if 'user_id' not in session:
        return jsonify({'error': '未登录'}), 401
    
    # 只有管理员可以管理用户权限
    if session.get('role') != 'admin':
        return jsonify({'error': '权限不足'}), 403
    
    # GET - 获取指定用户的权限
    if request.method == 'GET':
        try:
            conn = get_db()
            cursor = conn.cursor(); cursor.execute("""
                SELECT page_name, can_view, can_edit, can_delete
                FROM user_permissions
                WHERE user_id = ?
            """, (user_id,))
            
            permissions = {}
            for row in cursor.fetchall():
                page_name, can_view, can_edit, can_delete = row
                permissions[page_name] = {
                    'can_view': bool(can_view),
                    'can_edit': bool(can_edit),
                    'can_delete': bool(can_delete)
                }
            
            conn.close()
            return jsonify(permissions)
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    # PUT - 更新用户权限
    elif request.method == 'PUT':
        data = request.json
        permissions = data.get('permissions', {})
        
        try:
            conn = get_db()
            
            # 删除旧权限
            conn.cursor().execute("DELETE FROM user_permissions WHERE user_id = ?", (user_id,))
            
            # 插入新权限
            for page_name, perms in permissions.items():
                conn.cursor().execute("""
                    INSERT INTO user_permissions 
                    (user_id, page_name, can_view, can_edit, can_delete)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    user_id, 
                    page_name, 
                    perms.get('can_view', False),
                    perms.get('can_edit', False),
                    perms.get('can_delete', False)
                ))
            
            conn.commit()
            
            # 如果修改的是当前登录用户的权限,立即刷新session中的权限
            immediate_effect = False
            if session.get('user_id') == user_id:
                # 重新加载权限到session
                cursor = conn.cursor(); cursor.execute("""
                    SELECT page_name, can_view, can_edit, can_delete
                    FROM user_permissions
                    WHERE user_id = ?
                """, (user_id,))
                
                # 更新session中的权限
                session_permissions = {}
                for row in cursor.fetchall():
                    page_name, can_view, can_edit, can_delete = row
                    session_permissions[page_name] = {
                        'can_view': bool(can_view),
                        'can_edit': bool(can_edit),
                        'can_delete': bool(can_delete)
                    }
                
                # 将权限存储到session中(如果需要的话)
                # 注意:当前实现中权限是实时从数据库查询的,这里只是示例
                immediate_effect = True
            
            conn.close()
            
            return jsonify({'success': True, 'immediate_effect': immediate_effect})
        except Exception as e:
            return jsonify({'error': str(e)}), 500

# 更新用户信息（仅管理员）
@app.route('/api/users/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    if 'user_id' not in session:
        return jsonify({'error': '未登录'}), 401
    
    # 只有管理员可以更新用户信息
    if session.get('role') != 'admin':
        return jsonify({'error': '权限不足'}), 403
    
    data = request.json
    role = data.get('role')
    is_active = data.get('is_active')
    
    try:
        conn = get_db()
        
        if role is not None:
            conn.cursor().execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))
        
        if is_active is not None:
            conn.cursor().execute("UPDATE users SET is_active = ? WHERE id = ?", (is_active, user_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 删除用户（仅管理员）
@app.route('/api/users/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    if 'user_id' not in session:
        return jsonify({'error': '未登录'}), 401
    
    # 只有管理员可以删除用户
    if session.get('role') != 'admin':
        return jsonify({'error': '权限不足'}), 403
    
    # 不能删除自己
    if session.get('user_id') == user_id:
        return jsonify({'error': '不能删除自己'}), 400
    
    try:
        conn = get_db()
        conn.cursor().execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 新增API：设置揽收预估数据
@app.route('/api/pickup_forecast', methods=['POST'])
def set_pickup_forecast():
    try:
        data = request.json
        forecast_date = data.get('date')
        forecast_amount = data.get('amount')
        
        if not forecast_date or forecast_amount is None:
            return jsonify({'error': '请提供日期和预估数量'}), 400
        
        conn = get_db()
        
        # 检查是否已存在该日期的预估数据
        cursor = conn.cursor(); cursor.execute(convert_query_placeholders("SELECT id FROM pickup_forecast WHERE forecast_date = ?"), (forecast_date,))
        existing_record = cursor.fetchone()
        
        if existing_record:
            # 更新现有记录
            conn.cursor().execute("""UPDATE pickup_forecast 
                SET forecast_amount = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE forecast_date = ?""", (forecast_amount, forecast_date))
        else:
            # 插入新记录
            conn.cursor().execute("""INSERT INTO pickup_forecast 
                (forecast_date, forecast_amount) 
                VALUES (?, ?)""", (forecast_date, forecast_amount))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 新增API：获取揽收预估数据
@app.route('/api/pickup_forecast')
def get_pickup_forecast():
    try:
        # 获取日期参数，默认为今天
        date_str = request.args.get('date')
        
        if not date_str:
            # 获取系统当前日期
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        conn = get_db()
        cursor = conn.cursor(); cursor.execute(convert_query_placeholders("SELECT forecast_amount FROM pickup_forecast WHERE forecast_date = ?"), (date_str,))
        record = cursor.fetchone()
        conn.close()
        
        if record:
            return jsonify({'amount': record[0]})
        else:
            return jsonify({'amount': 0})  # 如果没有预估数据，返回0
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# 模块级别初始化 - Gunicorn 导入模块时会执行
# 这确保数据库在应用启动时被初始化
print("[模块加载] 开始初始化应用...")
try:
    initialize_app()
    print("[模块加载] 应用初始化成功")
except Exception as e:
    print(f"[模块加载] 警告: 初始化失败 - {e}")
    import traceback
    traceback.print_exc()

if __name__ == "__main__":
    init_db()
    
    # 启动每日重置检查线程
    reset_thread = threading.Thread(target=daily_reset_check, daemon=True)
    reset_thread.start()
    
    # 从环境变量获取主机和端口配置
    host = os.environ.get('HOST', HOST)
    port = int(os.environ.get('PORT', PORT))
    
    print(f"Starting server on {host}:{port}")
    app.run(debug=True, host=host, port=port)