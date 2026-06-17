#!/usr/bin/env python3
import sys
import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import requests
from datetime import datetime, time, timedelta
from gofo_config import get_gofo_token
from gofo_vehicle_arrival import _parse_la_dt, LA_TZ

token = get_gofo_token()
h = {
    "Admin-Token": token,
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
    "User-Time-Zone": "America/Los_Angeles",
    "Channel-Id": "us",
    "lang": "zh",
}
url = "https://dms.gofoexpress.com/prod-api/dbu_tms/api/task/transportTask/pageList"
now = datetime.now(LA_TZ)
today = now.date()


def window_for_day(d):
    ws = LA_TZ.localize(datetime.combine(d, time.min))
    we = LA_TZ.localize(datetime.combine(d, time(23, 59, 59)))
    if d == today:
        we = now
    return ws, we


def agg(recs, field):
    n = len(recs)
    boxes = sum(int(r.get("transitBoxesTotal") or 0) for r in recs)
    tickets = sum(int(r.get("waybillTotal") or 0) for r in recs)
    return n, boxes, tickets


def fetch_all(time_field, day, statuses=None):
    statuses = statuses or ["1", "2", "3", "4", "5", "6"]
    ws, we = window_for_day(day)
    seen = set()
    matched = []
    for page in range(1, 30):
        data = {
            "taskNos": [],
            "supplierIdList": [],
            "taskStatusList": statuses,
            "lineIdList": [],
            "transportationTypeList": [],
            "placeOfOriginList": [],
            "destinationList": [148],
            "vehicleAttributeList": [],
            "dispatchTypeList": [],
            "departTypeList": [],
            "linePointIdList": [],
            "licensePlateNoList": [],
            "trailerNoList": [],
            "forceTaskStatusList": [1, 2, 3, 4, 5, 6],
        }
        if time_field == "actualArrival":
            data["actualArrivalStartTimeStr"] = ws.strftime("%Y-%m-%d %H:%M:%S")
            data["actualArrivalEndTimeStr"] = we.strftime("%Y-%m-%d %H:%M:%S")
        elif time_field == "plannedArrival":
            data["plannedArrivalStartTimeStr"] = ws.strftime("%Y-%m-%d %H:%M:%S")
            data["plannedArrivalEndTimeStr"] = we.strftime("%Y-%m-%d %H:%M:%S")
        j = requests.post(url, headers=h, json={"data": data, "pageNum": page, "pageSize": 200}, timeout=45).json()
        recs = (j.get("data") or {}).get("records") or []
        if not recs:
            break
        for rec in recs:
            if rec.get("destination") != "CNO.H":
                continue
            dt = _parse_la_dt(rec.get("actualArrivalTime" if time_field == "actualArrival" else "plannedArrivalTime"))
            if dt is None or dt < ws or dt > we:
                continue
            tn = rec.get("taskNo")
            if tn in seen:
                continue
            seen.add(tn)
            matched.append(rec)
        if len(recs) < 200:
            break
    return matched


for label, tf, day in [
    ("today arrived actual", "actualArrival", today),
    ("today expected planned", "plannedArrival", today),
    ("tomorrow expected planned", "plannedArrival", today + timedelta(days=1)),
    ("day+2 expected planned", "plannedArrival", today + timedelta(days=2)),
]:
    m = fetch_all(tf, day)
    print(label, agg(m, tf))
