import sqlite3
import json

def main():
    conn = sqlite3.connect('inbound.db')
    cur = conn.cursor()
    cur.execute("SELECT task_no, actual_departure_time, raw_json FROM gofo_tms_shuttle_completed WHERE record_date='2026-05-20' LIMIT 5")
    rows = cur.fetchall()
    for task_no, dep_time, raw_json in rows:
        print(f"Task: {task_no}, dep_time: {dep_time}")
        try:
            j = json.loads(raw_json)
            # Print some keys of interest
            print("  Raw keys of interest:")
            for k in ('actualDepartureTime', 'actualArrivalTime', 'plannedDepartureTime', 'plannedArrivalTime', 'createTime', 'updateTime'):
                print(f"    {k}: {j.get(k)}")
        except Exception as e:
            print(f"  Error loading JSON: {e}")
    conn.close()

if __name__ == '__main__':
    main()
