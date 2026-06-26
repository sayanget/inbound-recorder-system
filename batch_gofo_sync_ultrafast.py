import json
import logging
import os
import sys
import time
from collections import Counter
from datetime import datetime, timedelta

import requests

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from database import convert_placeholders, get_db_connection  # noqa: E402
from gofo_config import get_gofo_token  # noqa: E402

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

URL = "https://dms.gofoexpress.com/prod-api/ops/domain/operatelog/selectPageList"

PIECE_RATES = {
    'AAS Sorter 1': 0.095,
    'AAS Sorter 3': 0.095,
    'AAS Sorter 4': 0.095,
    'AAS Sorter 6': 0.12,
    'UNS Sorter 6': 0.095,
}


def sync_day_fast(target_date_str):
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
    next_date = target_date + timedelta(days=1)

    begin_time_str = f"{target_date.strftime('%Y-%m-%d')} 06:00:00"
    end_time_str = f"{next_date.strftime('%Y-%m-%d')} 05:59:59"

    token = get_gofo_token()
    headers = {
        "Admin-Token": token,
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
    }

    all_rows = []
    logging.info(f"⏳ Syncing {target_date_str} (24-hour block)")

    page_num = 1
    page_size = 1000

    while True:
        payload = {
            "containerNoType": "1",
            "createDeptId": 596,
            "scanBeginTime": begin_time_str,
            "scanEndTime": end_time_str,
            "scanTypeList": ["217"],
            "pageNum": page_num,
            "pageSize": page_size,
        }

        try:
            res = requests.post(URL, headers=headers, json=payload, timeout=60)
            if res.status_code == 200:
                data = res.json()
                if data.get("code") != 200:
                    logging.error(f"API Error: {data.get('msg')}")
                    break

                response_data = data.get("data") or {}
                rows = response_data.get("records", response_data.get("list", []))
                total = response_data.get("total", 0)

                if rows:
                    all_rows.extend(rows)
                    logging.info(f"   Fetched page {page_num} ({len(all_rows)}/{total})")

                if len(all_rows) >= total or not rows:
                    break
                page_num += 1
            else:
                logging.error(f"HTTP Error {res.status_code}")
                break
        except Exception as e:
            logging.error(f"Connection Error: {e}")
            time.sleep(5)
            continue

    if not all_rows:
        return 0

    seen = set()
    deduped = []
    for row in all_rows:
        key = (row.get('waybillNo'), row.get('scanTypeStr'), row.get('createByName'))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    counts: Counter = Counter()
    for row in deduped:
        name = row.get('createByName')
        if not name or 'Sorter' not in str(name):
            continue
        key = (name, row.get('scanTypeStr'), row.get('scanType'))
        counts[key] += 1

    if not counts:
        return 0

    summary_rows = []
    for (op, cat, code), pieces in counts.items():
        unit = PIECE_RATES.get(op, 0.0)
        summary_rows.append((
            target_date_str,
            begin_time_str,
            end_time_str,
            op,
            cat,
            code,
            pieces,
            unit,
            round(pieces * unit, 3),
        ))

    insert_sql, _ = convert_placeholders(
        """
        INSERT INTO gofo_piece_rate_summary (
            Record_Date, Period_Start, Period_End,
            Operator_Name, Scan_Category, Scan_Type_Code,
            Pieces, Unit_Price, Wages
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )
    delete_sql, _ = convert_placeholders(
        "DELETE FROM gofo_piece_rate_summary WHERE Record_Date = ?"
    )

    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(delete_sql, (target_date_str,))
        cur.executemany(insert_sql, summary_rows)

    return len(summary_rows)


def run():
    start_date = datetime(2026, 2, 10)
    end_date = datetime(2026, 3, 9)
    current_date = start_date
    while current_date <= end_date:
        ds = current_date.strftime("%Y-%m-%d")
        count = sync_day_fast(ds)
        logging.info(f"✅ Day {ds} finished: {count} operators saved")
        current_date += timedelta(days=1)


if __name__ == '__main__':
    run()
