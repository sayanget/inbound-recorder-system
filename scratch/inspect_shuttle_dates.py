import sqlite3

def main():
    conn = sqlite3.connect('inbound.db')
    cursor = conn.cursor()

    # Query gofo_tms_shuttle_split table
    print("=== gofo_tms_shuttle_split row distribution for 5 to 16 ===")
    cursor.execute("""
        SELECT record_date, actual_departure_date, SUBSTR(actual_departure_time, 1, 2) as hr, COUNT(*)
        FROM gofo_tms_shuttle_split
        WHERE hr >= '05' AND hr <= '16'
        GROUP BY record_date, actual_departure_date, hr
        ORDER BY record_date DESC, hr ASC
        LIMIT 50
    """)
    for r in cursor.fetchall():
        print(f"record_date={r[0]}, actual_departure_date={r[1]}, hour={r[2]} -> {r[3]} records")

    print("\n=== Check for NULL/empty actual_departure_date / actual_departure_time ===")
    cursor.execute("""
        SELECT COUNT(*), COUNT(actual_departure_date), COUNT(actual_departure_time)
        FROM gofo_tms_shuttle_split
    """)
    r = cursor.fetchone()
    print(f"Total split rows: {r[0]}, with departure date: {r[1]}, with departure time: {r[2]}")

    conn.close()

if __name__ == '__main__':
    main()
