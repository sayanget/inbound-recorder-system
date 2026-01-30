import sqlite3
import psycopg2
import os
import sys

# 本地数据库路径
SQLITE_DB_PATH = 'inbound.db'

# 远程数据库 URL
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_sqlite_conn():
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_pg_conn():
    if not DATABASE_URL:
        print("错误: 未设置 DATABASE_URL 环境变量")
        sys.exit(1)
    return psycopg2.connect(DATABASE_URL)

def to_int(val):
    if val is None or val == '':
        return None
    try:
        return int(float(val))
    except:
        return None

def migrate_table(table_name, columns, boolean_columns=None, integer_columns=None):
    if boolean_columns is None: boolean_columns = []
    if integer_columns is None: integer_columns = []
        
    print(f"正在迁移表 {table_name}...")
    
    # 读取 SQLite 数据
    try:
        sqlite_conn = get_sqlite_conn()
        cursor = sqlite_conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        sqlite_conn.close()
    except Exception as e:
        print(f"  - 读取本地表失败: {e}")
        return

    if not rows:
        print(f"  - 表 {table_name} 为空")
        return

    # 连接 PG
    try:
        pg_conn = get_pg_conn()
        pg_cursor = pg_conn.cursor()
        
        # 清空目标表
        print(f"  - 清空远程表 {table_name}...")
        pg_cursor.execute(f"TRUNCATE TABLE {table_name} RESTART IDENTITY CASCADE")
        
        # 准备插入语句
        placeholders = ["%s"] * len(columns)
        cols_str = ", ".join(columns)
        sql = f"INSERT INTO {table_name} ({cols_str}) VALUES ({', '.join(placeholders)})"
        
        success_count = 0
        fail_count = 0
        
        for row in rows:
            values = []
            for col in columns:
                try:
                    val = row[col]
                    
                    # Boolean 处理
                    if col in boolean_columns:
                        val = bool(val) if val is not None else None
                        
                    # Integer 处理
                    if col in integer_columns:
                        val = to_int(val)
                        
                    values.append(val)
                except IndexError:
                     values.append(None)
                except Exception:
                    values.append(None)
            
            try:
                pg_cursor.execute(sql, values)
                success_count += 1
            except Exception as e:
                if fail_count < 5:
                    print(f"  - 插入失败 (ID {values[0] if values else '?'}): {e}")
                fail_count += 1
                pg_conn.rollback() 
                
        pg_conn.commit()
        print(f"  - 结果: 成功 {success_count} 条, 失败 {fail_count} 条")
        
        # 重置序列
        if 'id' in columns:
            try:
                pg_cursor.execute(f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), coalesce(max(id), 1)) FROM {table_name}")
            except Exception as e:
                print(f"  - 重置序列警告: {e}")

        pg_conn.close()
        
    except Exception as e:
        print(f"  - 表级迁移错误: {e}")

def main():
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"错误: 找不到本地数据库 {SQLITE_DB_PATH}")
        return

    print("=== 开始数据迁移: SQLite -> PostgreSQL ===")
    
    # 1. Users
    migrate_table('users', 
                 ['id', 'username', 'password_hash', 'role', 'created_at', 'is_active'],
                 boolean_columns=['is_active'])

    # 2. Permissions
    migrate_table('user_permissions',
                 ['user_id', 'page_name', 'can_view', 'can_edit', 'can_delete'],
                 boolean_columns=['can_view', 'can_edit', 'can_delete'])
                 
    # 3. Inbound Records
    # 确保远程列存在
    try:
        pg_conn = get_pg_conn()
        cur = pg_conn.cursor()
        for col, dtype in [('duration', 'INTEGER'), ('unit', 'TEXT'), ('shift_type', 'TEXT')]:
            cur.execute(f"ALTER TABLE inbound_records ADD COLUMN IF NOT EXISTS {col} {dtype}")
        pg_conn.commit()
        pg_conn.close()
    except: pass

    migrate_table('inbound_records',
                 ['id', 'dock_no', 'vehicle_type', 'vehicle_no', 'unit', 'load_amount', 'pieces', 
                  'time_slot', 'shift_type', 'remark', 'created_at', 'duration'],
                 integer_columns=['dock_no', 'load_amount', 'pieces', 'duration'])
                  
    # 4. Sorting Records
    migrate_table('sorting_records',
                 ['id', 'sorting_time', 'pieces', 'remark', 'created_at'],
                 integer_columns=['pieces'])
                 
    # 5. Pickup Forecast
    migrate_table('pickup_forecast',
                 ['id', 'forecast_date', 'forecast_amount', 'created_at', 'updated_at'],
                 integer_columns=['forecast_amount'])

    # 6. Operation Logs
    migrate_table('operation_logs',
                 ['id', 'operation_type', 'table_name', 'record_id', 'old_data', 
                  'new_data', 'operator', 'created_at'],
                 integer_columns=['record_id'])

    print("\n=== 迁移全部完成! ===")

if __name__ == '__main__':
    main()
