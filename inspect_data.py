import sqlite3
import re

def check_int(val):
    if val is None or val == '': return True
    try:
        int(float(val)) # Handle 100.0 case
        return True
    except:
        return False

def check_date(val):
    if val is None or val == '': return True
    # Basic ISO check YYYY-MM-DD
    return re.match(r'^\d{4}-\d{2}-\d{2}', str(val)) is not None

with open('inspection.txt', 'w', encoding='utf-8') as f:
    conn = sqlite3.connect('inbound.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Users
    cursor.execute("SELECT id FROM users")
    user_ids = {row[0] for row in cursor.fetchall()}
    f.write(f"Users found: {len(user_ids)} IDs: {sorted(list(user_ids))}\n")
    
    # 2. Permissions orphans
    cursor.execute("SELECT DISTINCT user_id FROM user_permissions")
    perm_user_ids = {row[0] for row in cursor.fetchall()}
    orphans = perm_user_ids - user_ids
    if orphans:
        f.write(f"Orphaned User Permissions for user_ids: {orphans}\n")
    else:
        f.write("No orphaned permissions.\n")
        
    # 3. Inbound Records
    f.write("\n--- Inbound Records Issues ---\n")
    int_cols = ['dock_no', 'load_amount', 'pieces', 'duration']
    
    cursor.execute("SELECT * FROM inbound_records")
    rows = cursor.fetchall()
    f.write(f"Total rows: {len(rows)}\n")
    
    issues_found = 0
    for row in rows:
        msgs = []
        for col in int_cols:
            val = row[col]
            if not check_int(val):
                msgs.append(f"{col}='{val}'")
        
        if not check_date(row['created_at']):
            msgs.append(f"created_at='{row['created_at']}'")
            
        if msgs:
            issues_found += 1
            if issues_found <= 20:
                f.write(f"ID {row['id']}: {', '.join(msgs)}\n")
                
    f.write(f"Total problem rows: {issues_found}\n")
    conn.close()
