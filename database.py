#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库抽象层 - 自动适配 SQLite 和 PostgreSQL

环境检测:
- 如果存在 DATABASE_URL 环境变量 → 使用 PostgreSQL
- 否则 → 使用 SQLite (默认,本地开发)
"""
import os
import sys
from contextlib import contextmanager

# 检测数据库类型
DATABASE_URL = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL')
USE_POSTGRES = DATABASE_URL is not None

if USE_POSTGRES:
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
        print(f"[数据库] 使用 PostgreSQL: {DATABASE_URL[:30]}...")
    except ImportError:
        print("[错误] PostgreSQL 驱动未安装!")
        print("生产环境部署请使用: pip install -r requirements-prod.txt")
        print("本地开发会自动使用 SQLite")
        USE_POSTGRES = False
        import sqlite3
        print("[数据库] 回退到 SQLite (本地模式)")
else:
    import sqlite3
    print("[数据库] 使用 SQLite (本地模式)")

# 获取 SQLite 数据库路径
def get_sqlite_db_path():
    """获取 SQLite 数据库路径"""
    if getattr(sys, 'frozen', False):
        # 打包后的 exe 环境
        return os.path.join(os.path.dirname(sys.executable), 'inbound.db')
    else:
        # 开发环境
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'inbound.db')

@contextmanager
def get_db_connection():
    """
    获取数据库连接的上下文管理器
    自动适配 SQLite 或 PostgreSQL
    """
    if USE_POSTGRES:
        # PostgreSQL 连接
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    else:
        # SQLite 连接
        db_path = os.environ.get('DATABASE_PATH') or get_sqlite_db_path()
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # 返回字典式结果
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

def convert_sql(sql):
    """
    转换 SQL 语法以适配不同数据库
    SQLite → PostgreSQL 语法转换
    """
    if not USE_POSTGRES:
        return sql
    
    # PostgreSQL 语法转换
    sql = sql.replace('INTEGER PRIMARY KEY AUTOINCREMENT', 'SERIAL PRIMARY KEY')
    sql = sql.replace('AUTOINCREMENT', '')
    sql = sql.replace('DATETIME', 'TIMESTAMP')
    
    return sql

def get_placeholder():
    """
    获取正确的 SQL 占位符
    SQLite: ?
    PostgreSQL: %s
    """
    return '%s' if USE_POSTGRES else '?'

def convert_placeholders(sql, params=None):
    """
    转换 SQL 占位符和参数
    返回: (转换后的SQL, 转换后的参数)
    """
    if not USE_POSTGRES:
        return sql, params
    
    # 将 ? 替换为 %s
    converted_sql = sql.replace('?', '%s')
    
    return converted_sql, params

def execute_query(query, params=None, fetch_one=False, fetch_all=False):
    """
    执行数据库查询的便捷函数
    
    Args:
        query: SQL 查询语句
        params: 查询参数
        fetch_one: 是否返回单条记录
        fetch_all: 是否返回所有记录
    
    Returns:
        查询结果或影响的行数
    """
    query, params = convert_placeholders(query, params)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params or ())
        
        if fetch_one:
            result = cursor.fetchone()
            return dict(result) if result else None
        elif fetch_all:
            results = cursor.fetchall()
            return [dict(row) for row in results]
        else:
            return cursor.rowcount

def get_db_type():
    """返回当前使用的数据库类型"""
    return 'PostgreSQL' if USE_POSTGRES else 'SQLite'

# 导出常用函数
__all__ = [
    'get_db_connection',
    'convert_sql',
    'get_placeholder',
    'convert_placeholders',
    'execute_query',
    'get_db_type',
    'USE_POSTGRES'
]
