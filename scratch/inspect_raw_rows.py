import sqlite3

def main():
    conn = sqlite3.connect('inbound.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT destination, actual_departure_date, actual_departure_time,
               actual_arrival_date, actual_arrival_time, record_date
        FROM gofo_tms_shuttle_split
        WHERE record_date = '2026-05-20'
        LIMIT 10
    """)
    print("=== Raw DB Rows for 2026-05-20 ===")
    for r in cursor.fetchall():
        print(r)
    conn.close()

if __name__ == '__main__':
    main()
