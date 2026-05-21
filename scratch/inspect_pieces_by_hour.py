import sqlite3

def main():
    conn = sqlite3.connect('inbound.db')
    cursor = conn.cursor()

    print("=== inbound_records SUM of pieces by hour ===")
    cursor.execute("""
        SELECT substr(time_slot, 1, 2) as hr, SUM(pieces), COUNT(*), SUM(CASE WHEN pieces > 0 THEN 1 ELSE 0 END)
        FROM inbound_records
        GROUP BY hr
        ORDER BY hr
    """)
    for r in cursor.fetchall():
        print(f"  Hour {r[0]}: Total pieces = {r[1]}, total rows = {r[2]}, rows with pieces > 0 = {r[3]}")

    print("\n=== sorting_records SUM of pieces by hour ===")
    cursor.execute("""
        SELECT substr(time_slot, 1, 2) as hr, SUM(pieces), SUM(manual_count), SUM(device_count), COUNT(*), SUM(CASE WHEN pieces > 0 THEN 1 ELSE 0 END)
        FROM sorting_records
        GROUP BY hr
        ORDER BY hr
    """)
    for r in cursor.fetchall():
        print(f"  Hour {r[0]}: Pieces={r[1]}, Manual={r[2]}, Device={r[3]}, rows={r[4]}, rows > 0 = {r[5]}")

    conn.close()

if __name__ == '__main__':
    main()
