import sqlite3
import os

def check_and_add_index():
    if getattr(sys, 'frozen', False):
        db_path = os.path.join(os.path.dirname(sys.executable), 'inbound.db')
    else:
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'inbound.db')
        
    print(f"Connecting to database at {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if index exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_inbound_records_is_synced'")
        if cursor.fetchone():
            print("Index 'idx_inbound_records_is_synced' already exists.")
        else:
            print("Creating index 'idx_inbound_records_is_synced'...")
            cursor.execute("CREATE INDEX idx_inbound_records_is_synced ON inbound_records (is_synced)")
            conn.commit()
            print("Index created successfully.")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    import sys
    check_and_add_index()
