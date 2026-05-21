import sqlite3

def main():
    conn = sqlite3.connect('inbound.db')
    cursor = conn.cursor()

    print("=== Recent 3 days of sorting_records ===")
    cursor.execute("""
        SELECT sorting_time, COUNT(*), SUM(pieces)
        FROM sorting_records
        GROUP BY sorting_time
        ORDER BY sorting_time DESC
        LIMIT 10
    """)
    for r in cursor.fetchall():
        print(f"  sorting_time: {r[0]} | count: {r[1]} | sum_pieces: {r[2]}")

    print("\n=== Recent 3 days of inbound_records ===")
    cursor.execute("""
        SELECT substr(created_at, 1, 10) as dt, COUNT(*), SUM(pieces)
        FROM inbound_records
        GROUP BY dt
        ORDER BY dt DESC
        LIMIT 10
    """)
    for r in cursor.fetchall():
        print(f"  created_at date: {r[0]} | count: {r[1]} | sum_pieces: {r[2]}")

    print("\n=== Recent 3 days of gofo_tms_shuttle_split ===")
    cursor.execute("""
        SELECT record_date, COUNT(*)
        FROM gofo_tms_shuttle_split
        GROUP BY record_date
        ORDER BY record_date DESC
        LIMIT 10
    """)
    for r in cursor.fetchall():
        print(f"  record_date: {r[0]} | count: {r[1]}")

    conn.close()

if __name__ == '__main__':
    main()
