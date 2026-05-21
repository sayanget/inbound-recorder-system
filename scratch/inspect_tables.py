import sqlite3

def main():
    conn = sqlite3.connect('inbound.db')
    cursor = conn.cursor()
    
    for tbl in ('inbound_records', 'sorting_records', 'gofo_tms_shuttle_split'):
        try:
            cursor.execute(f"PRAGMA table_info({tbl})")
            cols = [r[1] for r in cursor.fetchall()]
            print(f"Columns in {tbl}: {cols}")
        except Exception as e:
            print(f"Error for {tbl}: {e}")
            
    conn.close()

if __name__ == '__main__':
    main()
