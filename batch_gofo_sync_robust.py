import requests
import json
import logging
import sqlite3
import os
import time
import pandas as pd
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

URL = "https://dms.gofoexpress.com/prod-api/ops/domain/operatelog/selectPageList"
TOKEN = "eyJhbGciOiJIUzUxMiJ9.eyJsb2dpbl91c2VyX2tleSI6ImFiODkzZWYzLWU5OTgtNDAzYy1hYjYzLTAzNjIzZTg1MmI3ZCJ9.pg0tjItqwo4kTKsshyDoK8kF_J7miqpbUZNc0mqH26QeUltBvaa8Z_1mLZR9jITij8zi3fU6ioUkTYqH2dMAog"

PIECE_RATES = {
    'AAS Sorter 1': 0.095,
    'AAS Sorter 3': 0.095,
    'AAS Sorter 4': 0.095,
    'AAS Sorter 6': 0.12,
    'UNS Sorter 6': 0.095
}

def sync_day_robust(target_date_str):
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
    next_date = target_date + timedelta(days=1)
    
    begin_time_str = f"{target_date.strftime('%Y-%m-%d')} 06:00:00"
    end_time_str = f"{next_date.strftime('%Y-%m-%d')} 05:59:59"

    headers = {
        "Admin-Token": TOKEN,
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json"
    }

    all_rows = []
    logging.info(f"⏳ Syncing {target_date_str} (5-minute chunks)")

    start_dt = datetime.strptime(begin_time_str, "%Y-%m-%d %H:%M:%S")
    overall_end_dt = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")

    current_start_dt = start_dt
    while current_start_dt <= overall_end_dt:
        current_end_dt = current_start_dt + timedelta(minutes=5) - timedelta(seconds=1)
        if current_end_dt > overall_end_dt:
            current_end_dt = overall_end_dt

        chunk_begin_str = current_start_dt.strftime("%Y-%m-%d %H:%M:%S")
        chunk_end_str = current_end_dt.strftime("%Y-%m-%d %H:%M:%S")
        
        page_num = 1
        page_size = 500
        chunk_rows_count = 0
        
        while True:
            payload = {
                "containerNoType": "1",
                "createDeptId": 596,
                "scanBeginTime": chunk_begin_str,
                "scanEndTime": chunk_end_str,
                "scanTypeList": ["217"],
                "pageNum": page_num,
                "pageSize": page_size
            }

            try:
                res = requests.post(URL, headers=headers, json=payload, timeout=60)
                if res.status_code == 200:
                    data = res.json()
                    if data.get("code") == 200:
                        response_data = data.get("data") or {}
                        rows = response_data.get("records", response_data.get("list", []))
                        total = response_data.get("total", 0)
                        if rows:
                            all_rows.extend(rows)
                            chunk_rows_count += len(rows)
                        if chunk_rows_count >= total or not rows:
                            break
                        page_num += 1
                    else:
                        logging.warning(f"   API Warning ({chunk_begin_str}): {data.get('msg')}")
                        time.sleep(5)
                        continue
                else:
                    logging.warning(f"   HTTP Error {res.status_code}")
                    break
            except Exception as e:
                logging.error(f"   Network Error ({chunk_begin_str}): {e}")
                time.sleep(5)
                break

        current_start_dt = current_end_dt + timedelta(seconds=1)

    if not all_rows:
        return 0

    df = pd.DataFrame(all_rows)
    if 'waybillNo' in df.columns:
        df.drop_duplicates(subset=['waybillNo', 'scanTypeStr', 'createByName'], inplace=True)
    
    summary_df = df.groupby(['createByName', 'scanTypeStr', 'scanType']).size().reset_index(name='Pieces')
    summary_df = summary_df[summary_df['createByName'].str.contains('Sorter', na=False)].copy()
    
    if summary_df.empty:
        return 0

    summary_df['Record_Date'] = target_date_str
    summary_df['Period_Start'] = begin_time_str
    summary_df['Period_End'] = end_time_str
    summary_df.rename(columns={'createByName': 'Operator_Name', 'scanTypeStr': 'Scan_Category', 'scanType': 'Scan_Type_Code'}, inplace=True)
    summary_df['Unit_Price'] = summary_df['Operator_Name'].apply(lambda x: PIECE_RATES.get(x, 0.0))
    summary_df['Wages'] = (summary_df['Pieces'] * summary_df['Unit_Price']).round(3)
    
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'inbound.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM gofo_piece_rate_summary WHERE Record_Date = ?", (target_date_str,))
    summary_df.to_sql('gofo_piece_rate_summary', conn, if_exists='append', index=False)
    conn.commit()
    conn.close()
    return len(summary_df)

def run():
    start_date = datetime(2026, 2, 10)
    end_date = datetime(2026, 3, 9)
    current_date = start_date
    while current_date <= end_date:
        ds = current_date.strftime("%Y-%m-%d")
        count = sync_day_robust(ds)
        logging.info(f"✅ Day {ds} finished: {count} operators saved")
        current_date += timedelta(days=1)

if __name__ == '__main__':
    run()
