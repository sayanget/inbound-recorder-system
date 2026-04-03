import sqlite3

conn = sqlite3.connect('inbound.db')
cursor = conn.cursor()

# Get count of bad rows
cursor.execute("SELECT COUNT(*) FROM feishu_transport_data WHERE record_date LIKE 'TEXT%'")
bad_rows = cursor.fetchone()[0]
print(f"Bad rows identified: {bad_rows}")

# Delete them
cursor.execute("DELETE FROM feishu_transport_data WHERE record_date LIKE 'TEXT%'")

# Count remaining valid rows
cursor.execute("SELECT COUNT(*) FROM feishu_transport_data")
total_rows = cursor.fetchone()[0]
print(f"Valid rows remaining: {total_rows}")

# Get distinct dates
cursor.execute("SELECT DISTINCT record_date FROM feishu_transport_data")
dates = cursor.fetchall()
print(f"Distinct valid dates: {[r[0] for r in dates]}")

conn.commit()
conn.close()
