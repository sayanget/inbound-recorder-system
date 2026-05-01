#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
拉取 GoFO DMS - TMS「短驳/运输任务」页面（vehicleManagement/transportationManagement/shuttle）
按筛选「状态=已完成 / 始发地=CNO.H」的当天全部任务，按「实际发车时间(actualDepartureTime)」
切成每个整点小时一桶，落到本地 SQLite 新表 gofo_tms_shuttle_completed。

接口：
  POST https://dms.gofoexpress.com/prod-api/dbu_tms/api/task/transportTask/pageList
  taskStatusList=["5"]            状态=已完成
  placeOfOriginList=[148]         CNO.H 中转 ID
  actualDepartureStartTimeStr / actualDepartureEndTimeStr  时间类型=【实际发车时间】（与页面 UI 选择对应）
  返回字段 actualDepartureTime / actualArrivalTime 原样存，不做时区换算

HTTP 头携带 User-Time-Zone=America/Los_Angeles 与浏览器一致；日期字符串按调用方传入原样提交，不做本地换算。

用法：
  python scripts/sync_tms_shuttle_completed.py                       # 抓"今天"（系统本地日期）
  python scripts/sync_tms_shuttle_completed.py --date 2026-04-28
  python scripts/sync_tms_shuttle_completed.py --last-week           # 上周 周一~周日
  python scripts/sync_tms_shuttle_completed.py --start 2026-04-20 --end 2026-04-26
  python scripts/sync_tms_shuttle_completed.py --hour-summary        # 同时打印每小时计数
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from gofo_config import get_gofo_token  # noqa: E402

URL = "https://dms.gofoexpress.com/prod-api/dbu_tms/api/task/transportTask/pageList"
TABLE = "gofo_tms_shuttle_completed"
TABLE_SPLIT = "gofo_tms_shuttle_split"
DB_PATH = (
    os.environ.get("DATABASE_PATH")
    or os.path.join(ROOT, "inbound.db")
)

CNO_H_ORIGIN_ID = 148
TASK_STATUS_COMPLETED = "5"
PAGE_SIZE = 200
MAX_PAGES = 500


def _headers(token: str) -> Dict[str, str]:
    return {
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {token}",
        "Admin-Token": token,
        "Content-Type": "application/json",
        "Origin": "https://dms.gofoexpress.com",
        "Referer": (
            "https://dms.gofoexpress.com/gofo-tms/"
            "vehicleManagement/transportationManagement/shuttle"
        ),
        "User-Time-Zone": "America/Los_Angeles",
        "timeZone": "GMT-0700",
        "Date-Time-Format": "MM/dd/yyyy HH:mm:ss",
        "lang": "zh",
        "Channel-Id": "us",
        "User-Agent": "Mozilla/5.0 (compatible; InboundGofo/1.0)",
    }


def _build_payload(
    page_num: int,
    page_size: int,
    day_str: str,
    *,
    origin_id: int,
    status_list: List[str],
) -> Dict[str, Any]:
    return {
        "data": {
            "taskNos": [],
            "supplierIdList": [],
            "taskStatusList": list(status_list),
            "lineIdList": [],
            "transportationTypeList": [],
            "placeOfOriginList": [origin_id],
            "destinationList": [],
            "vehicleAttributeList": [],
            "dispatchTypeList": [],
            "departTypeList": [],
            "linePointIdList": [],
            "forceTaskStatusList": [1, 2, 3, 4, 5, 6],
            "actualDepartureStartTimeStr": f"{day_str} 00:00:00",
            "actualDepartureEndTimeStr": f"{day_str} 23:59:59",
            "licensePlateNoList": [],
            "trailerNoList": [],
        },
        "pageNum": page_num,
        "pageSize": page_size,
    }


def _fetch_page(
    token: str,
    page_num: int,
    page_size: int,
    day_str: str,
    *,
    origin_id: int,
    timeout: int = 30,
    max_retries: int = 3,
) -> Tuple[List[Dict[str, Any]], Optional[int]]:
    body = _build_payload(
        page_num, page_size, day_str,
        origin_id=origin_id,
        status_list=[TASK_STATUS_COMPLETED],
    )
    last_err = ""
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(URL, headers=_headers(token), json=body, timeout=timeout)
            if r.status_code != 200:
                last_err = f"HTTP {r.status_code}: {r.text[:200]}"
                time.sleep(2 ** attempt)
                continue
            j = r.json()
            code = j.get("code")
            if code == 200:
                d = j.get("data") or {}
                recs = d.get("records") or d.get("list") or d.get("rows") or []
                total = d.get("total")
                try:
                    total_i = int(total) if total is not None else None
                except (TypeError, ValueError):
                    total_i = None
                return [r for r in recs if isinstance(r, dict)], total_i
            if code == 401:
                raise RuntimeError("Gofo Token 失效（401）。请重新登录刷新 token。")
            last_err = j.get("msg") or f"API code={code}"
            time.sleep(2 ** attempt)
        except requests.RequestException as e:
            last_err = str(e)
            time.sleep(2 ** attempt)
    raise RuntimeError(f"pageList 请求失败: {last_err}")


def _hour_bucket(actual_dep: Optional[str]) -> Optional[str]:
    """从 'YYYY-MM-DD HH:MM:SS' 抽出 'HH:00'。空值返回 None。"""
    if not actual_dep:
        return None
    s = str(actual_dep).strip()
    # 兼容形如 'YYYY-MM-DD HH:MM:SS' 与 'MM/DD/YYYY HH:MM:SS'
    parts = s.replace("/", "-").split(" ")
    if len(parts) < 2:
        return None
    hms = parts[1]
    hh = hms.split(":")[0]
    if hh.isdigit() and 0 <= int(hh) <= 23:
        return f"{int(hh):02d}:00"
    return None


def _ensure_table(cur: sqlite3.Cursor) -> None:
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
            record_date            TEXT NOT NULL,
            task_no                TEXT NOT NULL,
            actual_departure_hour  TEXT,
            task_status            TEXT,
            task_status_str        TEXT,
            line_name              TEXT,
            place_of_origin        TEXT,
            destination            TEXT,
            origin_transit_id      INTEGER,
            destination_transit_id INTEGER,
            transportation_type_str TEXT,
            license_plate_no       TEXT,
            trailer_no             TEXT,
            model_name             TEXT,
            supplier_name          TEXT,
            driver_type_str        TEXT,
            dispatch_type_str      TEXT,
            depart_type_str        TEXT,
            handling_mode_str      TEXT,
            planned_departure_time TEXT,
            actual_departure_time  TEXT,
            planned_arrival_time   TEXT,
            actual_arrival_time    TEXT,
            waybill_total          INTEGER,
            weight_total           REAL,
            transit_boxes_total    INTEGER,
            line_loading_rate      TEXT,
            carriage_cost          REAL,
            quotation_price        TEXT,
            total_mileage          REAL,
            operator_dept          TEXT,
            remark                 TEXT,
            create_time            TEXT,
            update_time            TEXT,
            raw_json               TEXT,
            fetched_at             TEXT,
            PRIMARY KEY (record_date, task_no)
        )
        """
    )
    cur.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{TABLE}_hour "
        f"ON {TABLE}(record_date, actual_departure_hour)"
    )
    cur.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{TABLE}_origin "
        f"ON {TABLE}(record_date, place_of_origin)"
    )
    cur.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE_SPLIT} (
            record_date            TEXT NOT NULL,
            task_no                TEXT NOT NULL,
            place_of_origin        TEXT,
            destination            TEXT,
            actual_departure_date  TEXT,
            actual_departure_time  TEXT,
            actual_arrival_date    TEXT,
            actual_arrival_time    TEXT,
            fetched_at             TEXT,
            PRIMARY KEY (record_date, task_no)
        )
        """
    )
    cur.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{TABLE_SPLIT}_origin "
        f"ON {TABLE_SPLIT}(record_date, place_of_origin)"
    )
    cur.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{TABLE_SPLIT}_dep "
        f"ON {TABLE_SPLIT}(actual_departure_date, actual_departure_time)"
    )


def _to_float(x: Any) -> Optional[float]:
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _to_int(x: Any) -> Optional[int]:
    if x is None or x == "":
        return None
    try:
        return int(x)
    except (TypeError, ValueError):
        try:
            return int(float(x))
        except (TypeError, ValueError):
            return None


def _split_dt(s: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """'YYYY-MM-DD HH:MM:SS' / 'MM/DD/YYYY HH:MM:SS' → (date, time)。空值返回 (None, None)。"""
    if not s:
        return None, None
    raw = str(s).strip().replace("/", "-")
    parts = raw.split(" ", 1)
    if len(parts) != 2:
        return raw or None, None
    return parts[0] or None, parts[1] or None


def _split_row_tuple(rec: Dict[str, Any], date_str: str, fetched_at: str) -> Optional[Tuple[Any, ...]]:
    task_no = rec.get("taskNo")
    if not task_no:
        return None
    dep_d, dep_t = _split_dt(rec.get("actualDepartureTime"))
    arr_d, arr_t = _split_dt(rec.get("actualArrivalTime"))
    return (
        date_str,
        str(task_no),
        rec.get("placeOfOrigin"),
        rec.get("destination"),
        dep_d, dep_t,
        arr_d, arr_t,
        fetched_at,
    )


def _row_tuple(rec: Dict[str, Any], date_str: str, fetched_at: str) -> Optional[Tuple[Any, ...]]:
    task_no = rec.get("taskNo")
    if not task_no:
        return None
    return (
        date_str,
        str(task_no),
        _hour_bucket(rec.get("actualDepartureTime")),
        rec.get("taskStatus"),
        rec.get("taskStatusStr"),
        rec.get("lineName"),
        rec.get("placeOfOrigin"),
        rec.get("destination"),
        _to_int(rec.get("originTransitId")),
        _to_int(rec.get("destinationTransitId")),
        rec.get("transportationTypeStr"),
        rec.get("licensePlateNo"),
        rec.get("trailerNo"),
        rec.get("modelName"),
        rec.get("supplierName"),
        rec.get("driverTypeStr"),
        rec.get("dispatchTypeStr"),
        rec.get("departTypeStr"),
        rec.get("handlingModeStr"),
        rec.get("plannedDepartureTime"),
        rec.get("actualDepartureTime"),
        rec.get("plannedArrivalTime"),
        rec.get("actualArrivalTime"),
        _to_int(rec.get("waybillTotal")),
        _to_float(rec.get("weightTotal")),
        _to_int(rec.get("transitBoxesTotal")),
        rec.get("lineLoadingRate"),
        _to_float(rec.get("carriageCost")),
        rec.get("quotationPrice"),
        _to_float(rec.get("totalMileage")),
        rec.get("operatorDept"),
        rec.get("remark"),
        rec.get("createTime"),
        rec.get("updateTime"),
        json.dumps(rec, ensure_ascii=False),
        fetched_at,
    )


_INSERT_SQL = f"""
INSERT INTO {TABLE} (
    record_date, task_no, actual_departure_hour,
    task_status, task_status_str, line_name,
    place_of_origin, destination,
    origin_transit_id, destination_transit_id,
    transportation_type_str, license_plate_no, trailer_no, model_name,
    supplier_name, driver_type_str, dispatch_type_str, depart_type_str, handling_mode_str,
    planned_departure_time, actual_departure_time,
    planned_arrival_time, actual_arrival_time,
    waybill_total, weight_total, transit_boxes_total, line_loading_rate,
    carriage_cost, quotation_price, total_mileage,
    operator_dept, remark, create_time, update_time,
    raw_json, fetched_at
) VALUES (?,?,?, ?,?,?, ?,?, ?,?, ?,?,?,?, ?,?,?,?,?, ?,?, ?,?, ?,?,?,?, ?,?,?, ?,?,?,?, ?,?)
ON CONFLICT(record_date, task_no) DO UPDATE SET
    actual_departure_hour  = excluded.actual_departure_hour,
    task_status            = excluded.task_status,
    task_status_str        = excluded.task_status_str,
    line_name              = excluded.line_name,
    place_of_origin        = excluded.place_of_origin,
    destination            = excluded.destination,
    origin_transit_id      = excluded.origin_transit_id,
    destination_transit_id = excluded.destination_transit_id,
    transportation_type_str = excluded.transportation_type_str,
    license_plate_no       = excluded.license_plate_no,
    trailer_no             = excluded.trailer_no,
    model_name             = excluded.model_name,
    supplier_name          = excluded.supplier_name,
    driver_type_str        = excluded.driver_type_str,
    dispatch_type_str      = excluded.dispatch_type_str,
    depart_type_str        = excluded.depart_type_str,
    handling_mode_str      = excluded.handling_mode_str,
    planned_departure_time = excluded.planned_departure_time,
    actual_departure_time  = excluded.actual_departure_time,
    planned_arrival_time   = excluded.planned_arrival_time,
    actual_arrival_time    = excluded.actual_arrival_time,
    waybill_total          = excluded.waybill_total,
    weight_total           = excluded.weight_total,
    transit_boxes_total    = excluded.transit_boxes_total,
    line_loading_rate      = excluded.line_loading_rate,
    carriage_cost          = excluded.carriage_cost,
    quotation_price        = excluded.quotation_price,
    total_mileage          = excluded.total_mileage,
    operator_dept          = excluded.operator_dept,
    remark                 = excluded.remark,
    create_time            = excluded.create_time,
    update_time            = excluded.update_time,
    raw_json               = excluded.raw_json,
    fetched_at             = excluded.fetched_at
"""

_INSERT_SPLIT_SQL = f"""
INSERT INTO {TABLE_SPLIT} (
    record_date, task_no, place_of_origin, destination,
    actual_departure_date, actual_departure_time,
    actual_arrival_date,   actual_arrival_time,
    fetched_at
) VALUES (?,?,?,?, ?,?, ?,?, ?)
ON CONFLICT(record_date, task_no) DO UPDATE SET
    place_of_origin       = excluded.place_of_origin,
    destination           = excluded.destination,
    actual_departure_date = excluded.actual_departure_date,
    actual_departure_time = excluded.actual_departure_time,
    actual_arrival_date   = excluded.actual_arrival_date,
    actual_arrival_time   = excluded.actual_arrival_time,
    fetched_at            = excluded.fetched_at
"""


def sync_day(
    day_str: str,
    *,
    origin_id: int = CNO_H_ORIGIN_ID,
    page_size: int = PAGE_SIZE,
    sleep_between: float = 0.2,
) -> Dict[str, Any]:
    token = get_gofo_token()
    page = 1
    fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows: List[Dict[str, Any]] = []
    total_expected: Optional[int] = None
    seen_tn: set = set()
    while page <= MAX_PAGES:
        recs, total = _fetch_page(
            token, page, page_size, day_str, origin_id=origin_id
        )
        if total is not None and total_expected is None:
            try:
                total_expected = int(total)
            except (TypeError, ValueError):
                pass
        if not recs:
            break
        added = 0
        for r in recs:
            tid = r.get("taskNo")
            if not tid:
                continue
            if tid not in seen_tn:
                seen_tn.add(tid)
                rows.append(r)
                added += 1
        if added == 0:
            # 本页无新单号（重复页或异常），避免死循环
            break
        page += 1
        if sleep_between > 0:
            time.sleep(sleep_between)
    else:
        print(
            f"警告: {day_str} 已达到最大页数 {MAX_PAGES}，可能未拉全",
            file=sys.stderr,
        )
    if total_expected is not None and len(seen_tn) != total_expected:
        print(
            f"警告: {day_str} API total={total_expected} 去重后 task 数={len(seen_tn)}，"
            f"合并行数={len(rows)}，请核对接口",
            file=sys.stderr,
        )

    conn = sqlite3.connect(DB_PATH)
    inserted = 0
    try:
        cur = conn.cursor()
        _ensure_table(cur)
        # 先把这一天清空再重灌，避免之前用 planned 过滤留下的“同 record_date 但 actualDeparture 非当天”的脏数据
        cur.execute(f"DELETE FROM {TABLE} WHERE record_date = ?", (day_str,))
        cur.execute(f"DELETE FROM {TABLE_SPLIT} WHERE record_date = ?", (day_str,))
        tuples = []
        split_tuples = []
        for rec in rows:
            t = _row_tuple(rec, day_str, fetched_at)
            if t is not None:
                tuples.append(t)
            st = _split_row_tuple(rec, day_str, fetched_at)
            if st is not None:
                split_tuples.append(st)
        if tuples:
            cur.executemany(_INSERT_SQL, tuples)
            inserted = len(tuples)
        if split_tuples:
            cur.executemany(_INSERT_SPLIT_SQL, split_tuples)
        conn.commit()

        cur.execute(
            f"SELECT actual_departure_hour, COUNT(*) FROM {TABLE} "
            f"WHERE record_date = ? GROUP BY actual_departure_hour ORDER BY actual_departure_hour",
            (day_str,),
        )
        per_hour = {(r[0] or "未知"): int(r[1]) for r in cur.fetchall()}
    finally:
        conn.close()

    return {
        "success": True,
        "date": day_str,
        "fetched": len(rows),
        "stored": inserted,
        "total_expected": total_expected,
        "per_hour": per_hour,
        "db_path": DB_PATH,
        "table": TABLE,
        "table_split": TABLE_SPLIT,
    }


def _date_range(start_str: str, end_str: str) -> List[str]:
    s = datetime.strptime(start_str, "%Y-%m-%d").date()
    e = datetime.strptime(end_str, "%Y-%m-%d").date()
    if s > e:
        s, e = e, s
    out = []
    d = s
    while d <= e:
        out.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    return out


def _last_week_range() -> Tuple[str, str]:
    """上周周一~周日（基于系统本地今天）。"""
    today = datetime.now().date()
    this_monday = today - timedelta(days=today.weekday())
    last_monday = this_monday - timedelta(days=7)
    last_sunday = last_monday + timedelta(days=6)
    return last_monday.strftime("%Y-%m-%d"), last_sunday.strftime("%Y-%m-%d")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="同步 TMS 短驳『已完成 + CNO.H』任务到本地 SQLite。"
    )
    ap.add_argument(
        "--date",
        help="指定单天 YYYY-MM-DD（默认系统本地今天，不做时区换算）",
    )
    ap.add_argument(
        "--start",
        help="日期范围起 YYYY-MM-DD（与 --end 配合使用）",
    )
    ap.add_argument(
        "--end",
        help="日期范围止 YYYY-MM-DD（与 --start 配合使用）",
    )
    ap.add_argument(
        "--last-week", action="store_true",
        help="抓上周（周一~周日，基于系统本地今天）",
    )
    ap.add_argument(
        "--origin-id",
        type=int,
        default=CNO_H_ORIGIN_ID,
        help=f"始发地 transit ID（默认 {CNO_H_ORIGIN_ID} = CNO.H）",
    )
    ap.add_argument(
        "--page-size", type=int, default=PAGE_SIZE,
    )
    ap.add_argument(
        "--sleep-between-days", type=float, default=0.3,
        help="日与日之间间隔秒数，默认 0.3",
    )
    ap.add_argument(
        "--hour-summary", action="store_true",
        help="单天模式下打印按小时计数",
    )
    args = ap.parse_args()

    if args.last_week:
        s, e = _last_week_range()
        days = _date_range(s, e)
    elif args.start and args.end:
        days = _date_range(args.start, args.end)
    elif args.start or args.end:
        print("--start 与 --end 必须同时提供", file=sys.stderr)
        return 2
    elif args.date:
        days = [args.date]
    else:
        days = [datetime.now().strftime("%Y-%m-%d")]

    grand_fetched = 0
    grand_stored = 0
    per_day = []
    for day in days:
        res = sync_day(day, origin_id=args.origin_id, page_size=args.page_size)
        grand_fetched += int(res.get("fetched") or 0)
        grand_stored += int(res.get("stored") or 0)
        per_day.append(res)
        print(
            f"[{res['date']}] 抓取 {res['fetched']} / total {res['total_expected']}，"
            f"入表 {res['stored']} 行"
        )
        if args.hour_summary and res.get("per_hour"):
            for hh, n in res["per_hour"].items():
                print(f"    {hh}  {n}")
        if args.sleep_between_days > 0 and day != days[-1]:
            time.sleep(args.sleep_between_days)

    if len(days) > 1:
        print(
            f"\n汇总: {len(days)} 天 [{days[0]} ~ {days[-1]}]，"
            f"抓取 {grand_fetched}，入表 {grand_stored}  →  "
            f"{per_day[0]['db_path']}\n"
            f"    详细表：{per_day[0]['table']}    拆分表：{per_day[0]['table_split']}"
        )
    else:
        r = per_day[0]
        print(
            f"DB → {r['db_path']}\n"
            f"    详细表：{r['table']}    拆分表：{r['table_split']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
