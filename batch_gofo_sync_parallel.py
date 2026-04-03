import requests
import json
import logging
import sqlite3
import os
import time
import pandas as pd
from datetime import datetime, timedelta
import concurrent.futures
import threading

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

db_lock = threading.Lock()

def sync_day_parallel(target_date_str):
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
    logging.info(f"⏳ Start Sync: {target_date_str}")

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
            "pageSize": page_size
        }

        try:
            res = requests.post(URL, headers=headers, json=payload, timeout=60)
            if res.status_code == 200:
                data = res.json()
                if data.get("code") != 200:
                    logging.error(f"   [{target_date_str}] API Error: {data.get('msg')}")
                    break
                    
                response_data = data.get("data") or {}
                rows = response_data.get("records", response_data.get("list", []))
                total = response_data.get("total", 0)
                
                if rows:
                    all_rows.extend(rows)
                
                if len(all_rows) >= total or not rows:
                    break
                page_num += 1
            else:
                logging.error(f"   [{target_date_str}] HTTP Error {res.status_code}")
                break
        except Exception as e:
            logging.error(f"   [{target_date_str}] Network Error: {e}")
            time.sleep(5)
            continue

    if not all_rows:
        logging.info(f"   [{target_date_str}] No data.")
        return 0

    df = pd.DataFrame(all_rows)
    if 'waybillNo' in df.columns:
        df.drop_duplicates(subset=['waybillNo', 'scanTypeStr', 'createByName'], inplace=True)
    
    summary_df = df.groupby(['createByName', 'scanTypeStr', 'scanType']).size().reset_index(name='Pieces')
    summary_df = summary_df[summary_df['createByName'].str.contains('Sorter', na=False)].copy()
    
    if summary_df.empty:
        logging.info(f"   [{target_date_str}] No Sorters found.")
        return 0

    summary_df['Record_Date'] = target_date_str
    summary_df['Period_Start'] = begin_time_str
    summary_df['Period_End'] = end_time_str
    summary_df.rename(columns={'createByName': 'Operator_Name', 'scanTypeStr': 'Scan_Category', 'scanType': 'Scan_Type_Code'}, inplace=True)
    
    summary_df['Unit_Price'] = summary_df['Operator_Name'].apply(lambda x: PIECE_RATES.get(x, 0.0))
    summary_df['Wages'] = (summary_df['Pieces'] * summary_df['Unit_Price']).round(3)
    
    # DB Update (Thread-safe)
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'inbound.db')
    with db_lock:
        try:
            conn = sqlite3.connect(db_path, timeout=30)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM gofo_piece_rate_summary WHERE Record_Date = ?", (target_date_str,))
            summary_df.to_sql('gofo_piece_rate_summary', conn, if_exists='append', index=False)
            conn.commit()
            conn.close()
            logging.info(f"✅ [{target_date_str}] Saved {len(summary_df)} operators.")
        except Exception as e:
            logging.error(f"   [{target_date_str}] DB Update Error: {e}")

    return len(summary_df)

def run():
    dates = []
    d = datetime(2026, 2, 10)
    while d <= datetime(2026, 3, 9):
        dates.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    
    logging.info(f"🚀 Starting Parallel Sync for {len(dates)} days (4 threads)")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        executor.map(sync_day_parallel, dates)
    logging.info("🎉 Global Sync Complete!")

if __name__ == '__main__':
    run()
