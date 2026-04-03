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

URL = "https://dms.gofoexpress.com/prod-api/ops/domain/operatelog/selectPageList"
# In a real app, this should ideally be in env vars or config.
# Token now resolved via gofo_config (DB/Env/File)

def fetch_and_summarize_gofo_piece_rate(target_date_str=None):
    """
    Fetch Gofo piece rate from 06:00 of the (target_date - 1) up to 06:00 of the target_date
    Save the aggregated counts by operator and scan category.
    """
    if not target_date_str:
        target_date_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
    next_date = target_date + timedelta(days=1)
    
    # "查询记录的起始日期为记录日期"
    # Example: target is 26th, we pull from 26th 06:00:00 to 27th 05:59:59
    begin_time_str = f"{target_date.strftime('%Y-%m-%d')} 06:00:00"
    end_time_str = f"{next_date.strftime('%Y-%m-%d')} 05:59:59"

    token = get_gofo_token()

    headers = {
        "Admin-Token": token,
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Connection": "keep-alive",
        "Date-Time-Format": "MM/dd/yyyy HH:mm:ss",
        "Origin": "https://dms.gofoexpress.com",
        "User-Agent": "Mozilla/5.0",
        "User-Time-Zone": "Local",
        "lang": "zh",
        "timeZone": "GMT-0800"
    }

    all_rows = []

    logging.info(f"⏳ Start fetching Gofo logs from {begin_time_str} to {end_time_str} in 5-min chunks")

    start_dt = datetime.strptime(begin_time_str, "%Y-%m-%d %H:%M:%S")
    overall_end_dt = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")

    current_start_dt = start_dt

    while current_start_dt <= overall_end_dt:
        current_end_dt = current_start_dt + timedelta(minutes=5) - timedelta(seconds=1)
        if current_end_dt > overall_end_dt:
            current_end_dt = overall_end_dt

        chunk_begin_str = current_start_dt.strftime("%Y-%m-%d %H:%M:%S")
        chunk_end_str = current_end_dt.strftime("%Y-%m-%d %H:%M:%S")
        
        logging.info(f"   -> Chunk {chunk_begin_str} to {chunk_end_str}")
        
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
                            rows = response_data.get("records", response_data.get("list", []))
                            total = response_data.get("total", 0)
                            
                            if rows:
                                all_rows.extend(rows)
                                chunk_rows_count += len(rows)
                            
                            if chunk_rows_count >= total or not rows:
                                break
                            
                            page_num += 1
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
                        time.sleep(2 ** retry_count) # Exponential backoff
                        
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
               msg = f"Max retries reached for chunk {chunk_begin_str}. Last error: {last_error}. Aborting sync."
               logging.error(msg)
               return {"success": False, "error": msg}
            
            # Since pagination might need another success loop, if we fetched all rows for this chunk, break the outer while True
            if chunk_rows_count >= total or not rows:
                break

        current_start_dt = current_end_dt + timedelta(seconds=1)

    if not all_rows:
        msg = f"No data found for the period {begin_time_str} to {end_time_str}."
        logging.info(msg)
        return {"success": True, "message": msg, "count": 0}

    # Aggregate Data using pandas
    df = pd.DataFrame(all_rows)
    
    # Deduplicate: one package scanned by the same person for the same operation counts as 1
    if not df.empty and 'waybillNo' in df.columns:
        df.drop_duplicates(subset=['waybillNo', 'scanTypeStr', 'createByName'], inplace=True)
    
    # We want to count the occurrences as 'pieces'
    summary_df = df.groupby(['createByName', 'scanTypeStr', 'scanType']).size().reset_index(name='Pieces')
    
    summary_df['Record_Date'] = target_date_str
    summary_df['Period_Start'] = begin_time_str
    summary_df['Period_End'] = end_time_str

    # Rename for DB conformity
    summary_df.rename(columns={
        'createByName': 'Operator_Name',
        'scanTypeStr': 'Scan_Category',
        'scanType': 'Scan_Type_Code'
    }, inplace=True)
    
    # Calculate Wages
    def get_unit_price(operator_name):
        rates = {
            'AAS Sorter 1': 0.095,
            'AAS Sorter 3': 0.095,
            'AAS Sorter 4': 0.095,
            'AAS Sorter 6': 0.12,
            'UNS Sorter 6': 0.095
        }
        # [FIX] Default rate for any Sorter not in the list
        return rates.get(operator_name, 0.095 if 'Sorter' in operator_name else 0.0)

    # Filter: Only keep actual Sorters (exclude machines and other roles)
    summary_df = summary_df[summary_df['Operator_Name'].str.contains('Sorter', na=False)].copy()
    
    summary_df['Unit_Price'] = summary_df['Operator_Name'].apply(get_unit_price)
    summary_df['Wages'] = (summary_df['Pieces'] * summary_df['Unit_Price']).round(3)
    
    # Reorder columns
    summary_df = summary_df[['Record_Date', 'Period_Start', 'Period_End', 'Operator_Name', 'Scan_Type_Code', 'Scan_Category', 'Pieces', 'Unit_Price', 'Wages']]

    # Archive to Database
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'inbound.db')
    table_name = 'gofo_piece_rate_summary'
    
    logging.info(f"⏳ Saving {len(summary_df)} aggregated records to local DB: {table_name}")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Ensure table exists
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {table_name} (
                Record_Date TEXT,
                Period_Start TEXT,
                Period_End TEXT,
                Operator_Name TEXT,
                Scan_Type_Code INTEGER,
                Scan_Category TEXT,
                Pieces INTEGER,
                Unit_Price REAL,
                Wages REAL
            )
        ''')
        
        # Migration: safely add new columns if upgrading from old version
        try: cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN Unit_Price REAL")
        except sqlite3.OperationalError: pass
        try: cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN Wages REAL")
        except sqlite3.OperationalError: pass
        
        # 每次更新只保存结果: delete the target date records before inserting
        cursor.execute(f"DELETE FROM {table_name} WHERE Record_Date = ?", (target_date_str,))
        conn.commit()
        
        # Insert new summarized data
        summary_df.to_sql(table_name, conn, if_exists='append', index=False)
        conn.close()
        
        # [FIX] Automatically merge into daily_cost_summary to ensure preview visibility
        try:
            update_daily_cost_summary(db_path, target_date_str)
            msg = f"✅ Database update successful! Pulled and merged {len(summary_df)} rows for {target_date_str} into summary preview."
        except Exception as merge_err:
             msg = f"✅ Decoupled success: Gofo data archived, but merge into summary failed: {merge_err}"
             
        logging.info(msg)
        return {"success": True, "message": msg, "count": len(summary_df)}
        
    except Exception as e:
        msg = f"Database Error: {str(e)}"
        logging.error(f"❌ {msg}")
        return {"success": False, "error": msg}

def update_daily_cost_summary(db_path, target_date_str):
    """
    Merge piece-rate data from gofo_piece_rate_summary into daily_cost_summary.
    """
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # 1. Aggregate piece rates by Agency
    cur.execute("""
        SELECT 
            CASE 
                WHEN Operator_Name LIKE 'AAS%' THEN 'AAS'
                WHEN Operator_Name LIKE 'UNS%' THEN 'UNS'
                ELSE 'OTHERS'
            END as Agency,
            SUM(Wages) as Piece_Wages,
            COUNT(DISTINCT Operator_Name) as Headcount
        FROM gofo_piece_rate_summary
        WHERE Record_Date = ?
        GROUP BY Agency
    """, (target_date_str,))
    piece_data = cur.fetchall()
    
    for row in piece_data:
        agency = row['Agency']
        wages = round(row['Piece_Wages'] or 0, 2)
        hc = row['Headcount']
        
        # Ensure row exists
        cur.execute("INSERT OR IGNORE INTO daily_cost_summary (Record_Date, Agency_Name) VALUES (?, ?)", (target_date_str, agency))
        # Update piece costs and increment headcount (caution: headcount might be shared)
        # For simplicity, we overwrite Piece_Cost_USD but only add to Headcount if it was 0 or from another source?
        # Actually, in Gofo pull, we just add the Gofo headcount.
        cur.execute("""
            UPDATE daily_cost_summary 
            SET Piece_Cost_USD = ?, Headcount = COALESCE(Headcount, 0) + ? 
            WHERE Record_Date = ? AND Agency_Name = ?
        """, (wages, hc, target_date_str, agency))

    # 2. Update Total Row
    cur.execute("INSERT OR IGNORE INTO daily_cost_summary (Record_Date, Agency_Name) VALUES (?, ?)", (target_date_str, '【当日总计】'))
    
    # Recalculate component sums for the total row
    cur.execute("""
        SELECT SUM(COALESCE(Hourly_Cost_USD, 0)), SUM(COALESCE(Piece_Cost_USD, 0)), SUM(COALESCE(Headcount, 0))
        FROM daily_cost_summary 
        WHERE Record_Date = ? AND Agency_Name != '【当日总计】'
    """, (target_date_str,))
    totals = cur.fetchone()
    if totals:
        th, tp, thc = totals
        cur.execute("""
            UPDATE daily_cost_summary 
            SET Hourly_Cost_USD = ?, Piece_Cost_USD = ?, Headcount = ?,
                Total_Cost_USD = COALESCE(?, 0) + COALESCE(?, 0)
            WHERE Record_Date = ? AND Agency_Name = '【当日总计】'
        """, (th or 0, tp or 0, thc or 0, th or 0, tp or 0, target_date_str))

    # 3. Update individual Total_Cost_USD
    cur.execute("""
        UPDATE daily_cost_summary 
        SET Total_Cost_USD = COALESCE(Hourly_Cost_USD, 0) + COALESCE(Piece_Cost_USD, 0)
        WHERE Record_Date = ?
    """, (target_date_str,))

    conn.commit()
    conn.close()
    logging.info(f"   -> Merged Gofo piece-rate into daily_cost_summary for {target_date_str}")

if __name__ == '__main__':
    # Test execution for "today"
    fetch_and_summarize_gofo_piece_rate()
