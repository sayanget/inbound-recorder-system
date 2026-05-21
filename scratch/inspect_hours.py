import sqlite3
from collections import defaultdict

def main():
    conn = sqlite3.connect('inbound.db')
    cursor = conn.cursor()

    print("=== inbound_records hourly counts ===")
    cursor.execute("""
        SELECT substr(time_slot, 1, 2) as hr, COUNT(*)
        FROM inbound_records
        GROUP BY hr
        ORDER BY hr
    """)
    for r in cursor.fetchall():
        print(f"  Hour {r[0]}: {r[1]} records")

    print("\n=== sorting_records hourly counts ===")
    cursor.execute("""
        SELECT substr(time_slot, 1, 2) as hr, COUNT(*)
        FROM sorting_records
        GROUP BY hr
        ORDER BY hr
    """)
    for r in cursor.fetchall():
        print(f"  Hour {r[0]}: {r[1]} records")

    print("\n=== gofo_tms_shuttle_split hourly counts ===")
    # actual_departure_time format is typically 'HH:MM:SS'
    cursor.execute("""
        SELECT substr(actual_departure_time, 1, 2) as hr, COUNT(*)
        FROM gofo_tms_shuttle_split
        GROUP BY hr
        ORDER BY hr
    """)
    for r in cursor.fetchall():
        print(f"  Hour {r[0]}: {r[1]} records")

    conn.close()

if __name__ == '__main__':
    main()
