import sqlite3
import os
import shutil
from datetime import datetime

db_path = 'inbound.db'
if not os.path.exists(db_path):
    db_path = r'd:\project\inbound_python_source\inbound.db'

print(f"Migrating database: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Rename existing table
    print("Renaming old table...")
    try:
        cursor.execute("ALTER TABLE outbound_records RENAME TO outbound_records_old")
    except sqlite3.OperationalError as e:
        if "no such table" in str(e):
            print("Table might already be renamed or not exist.")
        else:
            raise e

    # 2. Create new table WITHOUT unique constraint
    print("Creating new table...")
    create_query = """
    CREATE TABLE outbound_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        record_date TEXT NOT NULL,
        route_code TEXT NOT NULL,
        route_type TEXT NOT NULL,
        vehicle_count INTEGER DEFAULT 1,
        cost REAL DEFAULT 0,
        notes TEXT,
        created_by TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME
    );
    """
    cursor.execute(create_query)

    # 3. Copy data
    print("Copying data...")
    # Check columns in old table
    cursor.execute("PRAGMA table_info(outbound_records_old)")
    columns = [col[1] for col in cursor.fetchall()]
    cols_str = ", ".join(columns)
    
    # We can copy strict matching columns
    insert_sql = f"INSERT INTO outbound_records ({cols_str}) SELECT {cols_str} FROM outbound_records_old"
    cursor.execute(insert_sql)
    
    conn.commit()
    print(f"Migrated {cursor.rowcount} records.")

    # 4. Drop old table (Optional, maybe keep for safety for now? No, let's keep it renamed just in case)
    # cursor.execute("DROP TABLE outbound_records_old")
    
    conn.close()
    print("Migration complete.")

except Exception as e:
    print(f"Error: {e}")
    # If error, try to rollback rename?
    # Manual intervention might be needed if script fails halfway.
