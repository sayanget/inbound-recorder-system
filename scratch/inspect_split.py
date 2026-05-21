import sqlite3

def main():
    conn = sqlite3.connect('inbound.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    print("--- SPLIT records with record_date = '2026-05-20' ---")
    cursor.execute("""
        SELECT task_no, destination, actual_departure_date, actual_departure_time, record_date
        FROM gofo_tms_shuttle_split
        WHERE record_date = '2026-05-20'
    """)
    for r in cursor.fetchall():
        print(dict(r))

    print("\n--- SPLIT records with record_date = '2026-05-19' ---")
    cursor.execute("""
        SELECT task_no, destination, actual_departure_date, actual_departure_time, record_date
        FROM gofo_tms_shuttle_split
        WHERE record_date = '2026-05-19'
    """)
    for r in cursor.fetchall():
        print(dict(r))

    conn.close()

if __name__ == '__main__':
    main()
