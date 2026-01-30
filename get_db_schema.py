import sqlite3

def get_schema():
    conn = sqlite3.connect('inbound.db')
    cursor = conn.cursor()
    
    tables = ['inbound_records', 'sorting_records', 'pickup_forecast', 'users', 'user_permissions']
    
    with open('db_schema.txt', 'w', encoding='utf-8') as f:
        for table in tables:
            try:
                cursor.execute(f"PRAGMA table_info({table})")
                columns = [col[1] for col in cursor.fetchall()]
                f.write(f"Table: {table} Columns: {columns}\n")
            except Exception as e:
                f.write(f"Error reading {table}: {e}\n")
            
    conn.close()

if __name__ == '__main__':
    get_schema()
