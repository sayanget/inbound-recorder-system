import sqlite3

def add_column():
    conn = sqlite3.connect('inbound.db')
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE inbound_records ADD COLUMN is_synced INTEGER DEFAULT 0")
        print("Successfully added is_synced column")
    except Exception as e:
        print(f"Error (maybe column exists): {e}")
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    add_column()
