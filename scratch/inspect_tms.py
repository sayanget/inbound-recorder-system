import sqlite3
import json

def main():
    conn = sqlite3.connect('inbound.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT task_no, actual_departure_time, raw_json 
        FROM gofo_tms_shuttle_completed 
        WHERE record_date = '2026-05-20'
        LIMIT 1
    """)
    r = cursor.fetchone()
    if r:
        print("Task:", r['task_no'])
        print("actual_departure_time field in db:", r['actual_departure_time'])
        print("raw_json:")
        parsed = json.loads(r['raw_json'])
        print(json.dumps(parsed, indent=2, ensure_ascii=False))
    else:
        print("No task found for 2026-05-20")

    conn.close()

if __name__ == '__main__':
    main()


