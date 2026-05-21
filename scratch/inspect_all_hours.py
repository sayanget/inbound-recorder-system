import sqlite3

def main():
    conn = sqlite3.connect('inbound.db')
    cursor = conn.cursor()

    print("=== sorting_records for 2026-05-21 ===")
    cursor.execute("""
        SELECT time_slot, pieces, manual_count, device_count
        FROM sorting_records
        WHERE sorting_time = '2026-05-21'
        ORDER BY time_slot
    """)
    for r in cursor.fetchall():
        print(f"  slot: {r[0]} | pieces: {r[1]} | manual: {r[2]} | device: {r[3]}")

    conn.close()

if __name__ == '__main__':
    main()
