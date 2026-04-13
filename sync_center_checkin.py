import requests
import json
import logging
import sqlite3
import os
import time
import pandas as pd
from datetime import datetime, timedelta

from gofo_config import get_gofo_token

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def _parse_record_slot_from_api_row(row: dict, target_date_str: str) -> tuple:
    """
    从 details_v2 单行解析 (record_date YYYY-MM-DD, record_hour HH:00)。
    若接口未给时间维度，则使用 target_date_str + 当前整点（与旧逻辑兼容）。
    """
    rd = target_date_str
    rh = datetime.now().strftime("%H:00")
    if not isinstance(row, dict):
        return rd, rh
    for key in ("statDate", "bizDate", "reportDate", "date", "statTimeDate"):
        v = row.get(key)
        if v:
            s = str(v).strip()
            if len(s) >= 10 and s[4] == "-":
                rd = s[:10]
                break
    for key in ("reportHour", "statHour", "hour", "timeSlot", "hourStr", "timeHour"):
        v = row.get(key)
        if v is None or str(v).strip() == "":
            continue
        s = str(v).strip()
        try:
            if ":" in s:
                parts = s.split(":")
                h = int(parts[0]) % 24
                rh = f"{h:02d}:00"
            elif s.isdigit() and len(s) <= 2:
                rh = f"{int(s) % 24:02d}:00"
            else:
                continue
            break
        except (ValueError, IndexError):
            continue
    for key in ("createTime", "updateTime", "statTime", "reportTime"):
        v = row.get(key)
        if not v:
            continue
        try:
            s = str(v).replace("Z", "+00:00").replace("T", " ")
            if len(s) >= 16:
                t = datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
                rd = t.strftime("%Y-%m-%d")
                rh = t.strftime("%H:00")
                break
        except (ValueError, TypeError):
            continue
    return rd, rh

URL = "https://dms.gofoexpress.com/prod-api/dbu_report/common/magic/center/board/status/details_v2"

def fetch_center_checkin_data(target_date_str=None):
    """
    Fetch center check-in data (签入数) for a specific date mapping to 'CNO.H'.
    If no date is provided, defaults to today.
    """
    if not target_date_str:
        # Default to today
        target_date_str = datetime.now().strftime("%Y-%m-%d")

    # Time boundaries mapping the "viewing board" report structure (from 00:00:00 to now, or end of day)
    target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
    
    start_time_str = f"{target_date_str} 00:00:00"
    
    # If the target date is today, end time is now. If it's a past date, end time is 23:59:59.
    now = datetime.now()
    if target_date.date() == now.date():
        end_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    else:
        end_time_str = f"{target_date_str} 23:59:59"

    token = get_gofo_token()

    headers = {
        "Admin-Token": token,
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Connection": "keep-alive"
    }

    all_rows = []

    logging.info(f"⏳ Start fetching check-in stats for CNO.H from {start_time_str} to {end_time_str}")

    page_num = 1
    page_size = 500
    total_records = 0

    while True:
        payload = {
            "status": 2,
            "centerIds": [596],
            "timeArr": [],
            "endDateTime": "",
            "nextNodeList": [],
            "targetCenterId": 596, # 596 is CNO.H
            "startTime": start_time_str,
            "endTime": end_time_str,
            "pageNum": page_num,
            "pageSize": page_size,
            "dataType": 200,
            "groupType": 2
        }

        max_retries = 3
        retry_count = 0
        success = False
        last_error = ""

        while retry_count < max_retries and not success:
            try:
                res = requests.post(URL, headers=headers, json=payload, timeout=30)
                if res.status_code == 200:
                    data = res.json()
                    if data.get("code") == 200:
                        success = True
                        response_data = data.get("data") or {}
                        
                        rows = response_data.get("records", [])
                        total = response_data.get("total", 0)
                        
                        if rows:
                            all_rows.extend(rows)
                        
                        total_records = total
                        
                    elif data.get("code") == 401:
                        last_error = "Gofo API 登录失效 (Token Expired)"
                        logging.error(last_error)
                        return {"success": False, "error": last_error}
                    else:
                        last_error = f"API Error: {data.get('msg')}"
                        logging.warning(f"{last_error}, retrying... ({retry_count+1}/{max_retries})")
                        retry_count += 1
                        time.sleep(2 ** retry_count)
                else:
                    last_error = f"HTTP Error {res.status_code}"
                    logging.warning(f"{last_error}, retrying... ({retry_count+1}/{max_retries})")
                    retry_count += 1
                    time.sleep(2 ** retry_count) 
            except requests.exceptions.Timeout:
                last_error = "Request Timeout"
                logging.warning(f"{last_error}, retrying... ({retry_count+1}/{max_retries})")
                retry_count += 1
                time.sleep(2 ** retry_count)
            except Exception as e:
                last_error = f"Request Failed: {str(e)}"
                logging.warning(f"{last_error}, retrying... ({retry_count+1}/{max_retries})")
                retry_count += 1
                time.sleep(2 ** retry_count)
                
        if not success:
            msg = f"Max retries reached. Last error: {last_error}. Aborting sync."
            logging.error(msg)
            return {"success": False, "error": msg}

        # Check if we fetched all rows
        if len(all_rows) >= total_records or not rows:
            break
            
        page_num += 1

    if not all_rows:
        msg = f"No data found for the period {start_time_str} to {end_time_str}."
        logging.info(msg)
        return {"success": True, "message": msg, "count": 0}

    # Format Data（每行独立 record_date / record_hour，便于历史多日写入与图表横轴）
    df = pd.DataFrame(all_rows)
    slots = [_parse_record_slot_from_api_row(dict(r) if not isinstance(r, dict) else r, target_date_str) for r in all_rows]
    df["record_date"] = [s[0] for s in slots]
    df["record_hour"] = [s[1] for s in slots]
    df["start_time"] = start_time_str
    df["end_time"] = end_time_str

    # Select and rename columns mapping 
    rename_map = {
        'targetCenterId': 'target_center_id',
        'targetCenterName': 'target_center_name',
        'targetSiteId': 'target_site_id',
        'targetSiteName': 'target_site_name',
        'waybillCnt': 'waybill_cnt',
        'checkInWaybillCnt': 'check_in_waybill_cnt',
        'waitCheckInWaybillCnt': 'wait_check_in_waybill_cnt',
        'waitCheckOutWaybillCnt': 'wait_check_out_waybill_cnt',
        'waitCollectAndGroupCnt': 'wait_collect_and_group_cnt'
    }
    
    # Keep only required columns that exist in the dataframe
    columns_to_keep = ['record_date', 'record_hour', 'start_time', 'end_time'] + list(rename_map.keys())
    existing_cols = [c for c in columns_to_keep if c in df.columns]
    
    final_df = df[existing_cols].rename(columns=rename_map)

    # Archive to Database（与主应用 DATABASE_PATH 一致，便于同库读写）
    _root = os.path.dirname(os.path.abspath(__file__))
    db_path = os.environ.get("DATABASE_PATH") or os.path.join(_root, "inbound.db")
    table_name = 'gofo_center_checkin_stats'
    
    logging.info(f"⏳ Saving {len(final_df)} check-in records to local DB: {table_name}")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Ensure table exists
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {table_name} (
                record_date TEXT,
                record_hour TEXT,
                start_time TEXT,
                end_time TEXT,
                target_center_id INTEGER,
                target_center_name TEXT,
                target_site_id INTEGER,
                target_site_name TEXT,
                waybill_cnt INTEGER,
                check_in_waybill_cnt INTEGER,
                wait_check_in_waybill_cnt INTEGER,
                wait_check_out_waybill_cnt INTEGER,
                wait_collect_and_group_cnt INTEGER,
                PRIMARY KEY (record_date, record_hour, target_site_id)
            )
        ''')
        
        # Update/Insert using sqlite3 and executemany with UPSERT logic instead of pandas to_sql,
        # pandas to_sql doesn't support UPSERT on primary key conflict out of the box correctly without replace/fail.
        
        # Deduplicate using pandas just in case
        final_df = final_df.drop_duplicates(subset=['record_date', 'record_hour', 'target_site_id'])
        
        # Convert df to list of tuples
        records = final_df.to_dict('records')
        
        columns = list(final_df.columns)
        placeholders = ', '.join(['?'] * len(columns))
        columns_str = ', '.join(columns)
        
        update_str = ', '.join([f"{col} = excluded.{col}" for col in columns if col not in ['record_date', 'record_hour', 'target_site_id']])
        
        sql = f'''
            INSERT INTO {table_name} ({columns_str})
            VALUES ({placeholders})
            ON CONFLICT(record_date, record_hour, target_site_id) DO UPDATE SET {update_str}
        '''
        
        cursor.executemany(sql, [tuple(row[col] for col in columns) for row in records])
        conn.commit()
        conn.close()
        
        msg = f"✅ Database update successful! Pulled and merged {len(final_df)} rows for {target_date_str} check-in stats."
        logging.info(msg)
        return {"success": True, "message": msg, "count": len(final_df)}
        
    except Exception as e:
        msg = f"Database Error: {str(e)}"
        logging.error(f"❌ {msg}")
        return {"success": False, "error": msg}

if __name__ == '__main__':
    # Test execution for "today"
    fetch_center_checkin_data()
