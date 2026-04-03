import sqlite3
import os

# Use current directory for output to ensure accessibility
db_path = 'inbound.db'
output_file = 'audit_log.txt'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

with open(output_file, 'w', encoding='utf-8') as f:
    f.write("Checking 3/1/26 data in daily_cost_summary:\n")
    cur.execute("SELECT * FROM daily_cost_summary WHERE Record_Date = '3/1/26'")
    rows = cur.fetchall()
    for row in rows:
        f.write(str(dict(row)) + "\n")

    f.write("\nChecking matching data in gofo_piece_rate_summary:\n")
    cur.execute("SELECT * FROM gofo_piece_rate_summary WHERE record_date = '2026-03-01'")
    rows = cur.fetchall()
    for row in rows:
        f.write(str(dict(row)) + "\n")

conn.close()
print(f"Audit complete. Results in {os.path.abspath(output_file)}")
