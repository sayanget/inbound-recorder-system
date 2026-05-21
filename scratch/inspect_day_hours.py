import sqlite3

def main():
    conn = sqlite3.connect('inbound.db')
    cur = conn.cursor()
    
    # Query gofo_tms_shuttle_split
    cur.execute("""
        SELECT actual_departure_date, actual_departure_time, record_date
        FROM gofo_tms_shuttle_split
        WHERE record_date = '2026-05-20'
    """)
    rows = cur.fetchall()
    print(f"Total split rows for 2026-05-20: {len(rows)}")
    for r in sorted(rows, key=lambda x: (x[0] or '', x[1] or '')):
        print(f"  actual_departure_date={r[0]}, time={r[1]}, record_date={r[2]}")
        
    print("\n--- Summary by hour in database ---")
    cur.execute("""
        SELECT SUBSTR(actual_departure_time, 1, 2) as hr, COUNT(*)
        FROM gofo_tms_shuttle_split
        WHERE record_date = '2026-05-20'
        GROUP BY hr
        ORDER BY hr
    """)
    for r in cur.fetchall():
        print(f"  Hour {r[0]}: {r[1]} records")
        
    conn.close()

if __name__ == '__main__':
    main()
