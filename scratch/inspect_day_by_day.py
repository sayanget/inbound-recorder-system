import sqlite3

def main():
    conn = sqlite3.connect('inbound.db')
    cur = conn.cursor()
    
    # Get last 10 record_dates
    cur.execute("SELECT DISTINCT record_date FROM gofo_tms_shuttle_split ORDER BY record_date DESC LIMIT 10")
    dates = [r[0] for r in cur.fetchall()]
    
    for d in dates:
        print(f"\n--- record_date: {d} ---")
        cur.execute("""
            SELECT SUBSTR(actual_departure_time, 1, 2) as hr, COUNT(*)
            FROM gofo_tms_shuttle_split
            WHERE record_date = ?
            GROUP BY hr
            ORDER BY hr
        """, (d,))
        for r in cur.fetchall():
            print(f"  Hour {r[0]}: {r[1]} records")
            
    conn.close()

if __name__ == '__main__':
    main()
