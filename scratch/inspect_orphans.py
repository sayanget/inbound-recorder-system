import sqlite3
from datetime import datetime

def _hour_from_clock(s):
    if not s:
        return None
    parts = str(s).strip().split(':')
    if not parts or not str(parts[0]).isdigit():
        return None
    hi = int(parts[0])
    return hi if 0 <= hi <= 23 else None

def _tms_shuttle_normalize_date_time_cols(d_val, t_val):
    if d_val is None:
        return None, t_val
    d_s = str(d_val).strip()
    t_s = (str(t_val).strip() if t_val is not None else '')
    if t_s:
        return d_val, t_val
    u = d_s.replace('/', '-')
    if len(u) >= 11 and u[10] in 'Tt':
        u = u[:10] + ' ' + u[11:]
    if '.' in u:
        u = u.split('.')[0].strip()
    parts = u.split(None, 1)
    if len(parts) == 2 and ':' in parts[1]:
        return parts[0], parts[1]
    return d_val, t_val

def _tms_shuttle_pivot_parse_depart_dt(d_val, t_val):
    d_val, t_val = _tms_shuttle_normalize_date_time_cols(d_val, t_val)
    if d_val is None or t_val is None:
        return None
    ds = str(d_val).strip().replace('/', '-')
    ts = str(t_val).strip()
    if not ds or not ts:
        return None
    if '.' in ts:
        ts = ts.split('.')[0].strip()
    pairs = []
    for df in ('%Y-%m-%d', '%m-%d-%Y', '%d-%m-%Y'):
        for tf in ('%H:%M:%S', '%H:%M'):
            pairs.append((df, tf))
    cand_dts = [ds]
    if ' ' in ds:
        cand_dts.append(ds.split()[0])
    cand_ts = [ts]
    if len(ts) >= 8 and ts.count(':') >= 1:
        cand_ts.append(ts[:8])
    for dpart in cand_dts:
        for tpart in cand_ts:
            for df, tf in pairs:
                try:
                    return datetime.strptime(f'{dpart} {tpart}', f'{df} {tf}')
                except ValueError:
                    continue
    return None

def main():
    conn = sqlite3.connect('inbound.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT task_no, destination, actual_departure_date, actual_departure_time, record_date
        FROM gofo_tms_shuttle_split
    """)
    rows = cursor.fetchall()
    print("Total rows in gofo_tms_shuttle_split:", len(rows))

    unparseable = []
    null_cols = []
    for r in rows:
        dep_d = r['actual_departure_date']
        dep_t = r['actual_departure_time']
        if dep_d is None or dep_t is None:
            null_cols.append(dict(r))
            continue
        
        dt = _tms_shuttle_pivot_parse_depart_dt(dep_d, dep_t)
        if dt is None:
            unparseable.append(dict(r))

    print("\nRows with NULL date or time columns:", len(null_cols))
    for r in null_cols[:10]:
        print(r)

    print("\nRows with unparseable date/time columns:", len(unparseable))
    for r in unparseable[:10]:
        print(r)

    conn.close()

if __name__ == '__main__':
    main()
