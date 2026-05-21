import os
import sys
import json
import requests
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gofo_config import get_gofo_token

def main():
    try:
        token = get_gofo_token()
    except Exception as e:
        print(f"Error getting token: {e}")
        return

    url = "https://dms.gofoexpress.com/prod-api/dbu_tms/api/task/transportTask/pageList"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {token}",
        "Admin-Token": token,
        "Content-Type": "application/json",
        "Origin": "https://dms.gofoexpress.com",
        "Referer": "https://dms.gofoexpress.com/gofo-tms/vehicleManagement/transportationManagement/shuttle",
        "User-Time-Zone": "America/Los_Angeles",
        "timeZone": "GMT-0700",
        "Date-Time-Format": "MM/dd/yyyy HH:mm:ss",
        "lang": "zh",
        "Channel-Id": "us",
        "User-Agent": "Mozilla/5.0 (compatible; InboundGofo/1.0)",
    }

    # Query window: we can fetch May 19 to May 21
    payload = {
        "data": {
            "taskNos": [],
            "supplierIdList": [],
            "taskStatusList": ["5"], # Completed
            "lineIdList": [],
            "transportationTypeList": [],
            "placeOfOriginList": [148], # CNO.H
            "destinationList": [],
            "vehicleAttributeList": [],
            "dispatchTypeList": [],
            "departTypeList": [],
            "linePointIdList": [],
            "licensePlateNoList": [],
            "trailerNoList": [],
            "actualDepartureStartTimeStr": "2026-05-19 00:00:00",
            "actualDepartureEndTimeStr": "2026-05-21 23:59:59",
            "forceTaskStatusList": [1, 2, 3, 4, 5, 6]
        },
        "pageNum": 1,
        "pageSize": 500
    }

    print(f"Querying Gofo API from {payload['data']['actualDepartureStartTimeStr']} to {payload['data']['actualDepartureEndTimeStr']}...")
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        if r.status_code != 200:
            print(f"HTTP Error {r.status_code}: {r.text}")
            return
        res = r.json()
        if res.get("code") != 200:
            print(f"API Error {res.get('code')}: {res.get('msg')}")
            return
        
        data = res.get("data") or {}
        records = data.get("records") or data.get("list") or []
        print(f"Fetched {len(records)} records in total.")
        
        # Sort by actualDepartureTime
        records = [rec for rec in records if isinstance(rec, dict)]
        records.sort(key=lambda x: str(x.get("actualDepartureTime") or ""))
        
        print("\nAll raw records returned from API:")
        for i, rec in enumerate(records, 1):
            task_no = rec.get("taskNo")
            dept_time = rec.get("actualDepartureTime")
            origin = rec.get("placeOfOrigin")
            dest = rec.get("destination")
            status = rec.get("taskStatusStr")
            print(f"  {i:2d}. Task: {task_no} | Departure: {dept_time} | Origin: {origin} -> Dest: {dest} | Status: {status}")

    except Exception as e:
        print(f"Exception raised: {e}")

if __name__ == '__main__':
    main()
