import requests
import json
import sqlite3
import time
from datetime import datetime

TOKEN = 'eyJhbGciOiJIUzUxMiJ9.eyJsb2dpbl91c2VyX2tleSI6IjQxMTQ5MjhlLTMzMjItNDgwMi04Yjk1LTg2Y2FkZDIyNTU3OSJ9.4m5YLEL-Rb97ETumgf-Pq5bMrCGEhGXnM7ZFUDwTu0mOiVohtine_egF8bulfLdxEugWU92ZnabyjJaRYtjPRA'
headers = {
    'Admin-Token': TOKEN,
    'Authorization': f'Bearer {TOKEN}',
    'Content-Type': 'application/json',
    'User-Agent': 'Mozilla/5.0',
    'channel-id': 'us',
    'lang': 'zh'
}

def parse_gofo_value(val):
    if val is None: return 0
    if isinstance(val, (int, float)): return int(val)
    if not isinstance(val, str) or not val.strip(): return 0
    if '/' in val: 
        try:
            return int(val.split('/')[-1].replace(',', '').strip())
        except:
            return 0
    try:
        return int(val.replace(',', '').strip())
    except:
        return 0

def backfill():
    date_str = '2026-03-18'
    start_time = f'{date_str} 00:00:00'
    end_time = f'{date_str} 23:59:59'
    
    overview_url = "https://dms.gofoexpress.com/prod-api/dbu_report/common/magic/center/board/overview"
    chart_url = "https://dms.gofoexpress.com/prod-api/dbu_report/common/magic/center/board/operation/chart_v2"
    
    payload = {
        "centerIds": [596],
        "startTime": start_time,
        "endTime": end_time,
        "groupType": 2
    }
    
    print(f"Fetching chart data for {date_str}...")
    res = requests.post(chart_url, headers=headers, json=payload, timeout=20)
    chart_data = res.json().get('data', [])
    print(f"Found {len(chart_data)} hours.")
    
    conn = sqlite3.connect('inbound.db', timeout=30)
    cursor = conn.cursor()
    
    updates = 0
    for item in chart_data:
        hour_str = item.get('hour')
        if not hour_str: continue
        
        print(f"  Syncing hour {hour_str}...")
        hour_start = f"{hour_str}:00:00"
        hour_end = f"{hour_str}:59:59"
        hour_payload = {
            "centerIds": [596],
            "startTime": hour_start,
            "endTime": hour_end,
            "groupType": 2
        }
        
        try:
            h_res = requests.post(overview_url, headers=headers, json=hour_payload, timeout=15)
            h_data = h_res.json().get('data', {})
            
            pieces = parse_gofo_value(h_data.get('collectTotalCnt'))
            manual = parse_gofo_value(h_data.get('collectTotalCntArtificial'))
            device = parse_gofo_value(h_data.get('collectTotalCntDevice'))
            
            target_date = datetime.strptime(hour_str, '%Y-%m-%d %H').strftime('%Y-%m-%d')
            target_slot = datetime.strptime(hour_str, '%Y-%m-%d %H').strftime('%H:00')
            remark = f"Auto-backfilled (Fixed parsing bug)"
            
            cursor.execute("""
                UPDATE sorting_records 
                SET pieces = ?, manual_count = ?, device_count = ?, remark = ?
                WHERE sorting_time = ? AND time_slot = ?
            """, (pieces, manual, device, remark, target_date, target_slot))
            
            if cursor.rowcount == 0:
                # Insert if not exists
                cursor.execute("""
                    INSERT INTO sorting_records (sorting_time, pieces, remark, time_slot, created_at, manual_count, device_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (target_date, pieces, remark, target_slot, f"{date_str} 23:59:59", manual, device))
            
            updates += 1
            print(f"    Done: {pieces} pieces ({manual}M / {device}D)")
        except Exception as e:
            print(f"    Error on {hour_str}: {e}")
        
        time.sleep(0.5) # Avoid spamming
        
    conn.commit()
    conn.close()
    print(f"Finished backfill. Updated {updates} records.")

if __name__ == "__main__":
    backfill()
