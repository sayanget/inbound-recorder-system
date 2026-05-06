"""
GoFO 中心看板「集包数」弹窗（collectionPackage/popover）按小时抓取入库。

- 源：POST https://dms.gofoexpress.com/prod-api/dbu_report/common/magic/center/board/collectionPackage/popover
- 源中心：CNO.H（centerId=596）
- 目的组织类型：接口 **每条 record 带 destinType**（1=中心、2=站点、None 未归类），同一次响应可同时含中心与站点。
  弹窗里切换「目的组织类型」不改请求体，仅前端过滤展示。
- 粒度：接口一次请求返回 [startTime, endTime] 窗口内汇总值，没有按小时拆分字段。
  所以按整点循环窗口 [HH:00:00, (HH+1):00:00) 每小时一次，拿到那一小时的增量。
- 表：gofo_center_collect_stats，主键 (record_date, record_hour, source_center_id, destin_id)

对外函数：
  fetch_center_collect_hour(date_str, hour_int)          抓单个小时
  fetch_center_collect_day(date_str, upto_hour=None)     抓一整天（今天自动截到当前整点）
  fetch_center_collect_backfill(days=7)                  回补最近 N 天（中心+站点同上表）
"""
from __future__ import annotations

import logging
import os
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pytz
import requests

from gofo_config import get_gofo_token

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

URL = (
    "https://dms.gofoexpress.com/prod-api/"
    "dbu_report/common/magic/center/board/collectionPackage/popover"
)
DEFAULT_SOURCE_CENTER_ID = 596  # CNO.H
BOARD_TZ = pytz.timezone(os.environ.get("GOFO_BOARD_TIMEZONE", "America/Los_Angeles"))
TABLE_NAME = "gofo_center_collect_stats"
DB_PATH = (
    os.environ.get("DATABASE_PATH")
    or os.path.join(os.path.dirname(os.path.abspath(__file__)), "inbound.db")
)


def _headers(token: str) -> Dict[str, str]:
    return {
        "Admin-Token": token,
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "lang": "zh",
        "Channel-Id": "us",
        "User-Time-Zone": "America/Los_Angeles",
        "timeZone": "GMT-0700",
        "Date-Time-Format": "MM/dd/yyyy HH:mm:ss",
        "Origin": "https://dms.gofoexpress.com",
        "User-Agent": "Mozilla/5.0 (compatible; InboundGofo/1.0)",
    }


def _ensure_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            record_date       TEXT NOT NULL,
            record_hour       TEXT NOT NULL,
            source_center_id  INTEGER NOT NULL,
            destin_id         INTEGER NOT NULL,
            destin_name       TEXT,
            destin_type       INTEGER,
            waybill_cnt       INTEGER,
            package_cnt       INTEGER,
            start_time        TEXT,
            end_time          TEXT,
            fetched_at        TEXT,
            PRIMARY KEY (record_date, record_hour, source_center_id, destin_id)
        )
        """
    )
    cursor.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_date "
        f"ON {TABLE_NAME}(record_date, record_hour)"
    )
    cursor.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_destin "
        f"ON {TABLE_NAME}(destin_type, destin_name)"
    )


def _call_popover(
    token: str,
    start_time: str,
    end_time: str,
    center_id: int,
    timeout: int = 30,
    max_retries: int = 3,
) -> List[dict]:
    payload = {
        "destinIds": [],
        "dataType": 217,
        "type": "collectTotalCnt",
        "centerIds": [center_id],
        "pageNum": 1,
        "pageSize": 500,
        "startTime": start_time,
        "endTime": end_time,
    }
    last_err = ""
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(
                URL, json=payload, headers=_headers(token), timeout=timeout
            )
            if r.status_code != 200:
                last_err = f"HTTP {r.status_code}"
                time.sleep(2**attempt)
                continue
            body = r.json()
            code = body.get("code")
            if code == 200:
                return (body.get("data") or {}).get("records") or []
            if code == 401:
                raise RuntimeError("Gofo API 登录失效 (Token Expired)")
            last_err = body.get("msg") or f"API code={code}"
            time.sleep(2**attempt)
        except requests.RequestException as e:
            last_err = str(e)
            time.sleep(2**attempt)
    raise RuntimeError(f"popover 请求失败: {last_err}")


def _upsert_rows(
    rows: List[dict],
    *,
    record_date: str,
    record_hour: str,
    source_center_id: int,
    start_time: str,
    end_time: str,
) -> int:
    if not rows:
        return 0
    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    tuples = []
    for r in rows:
        dtype = r.get("destinType")
        did = r.get("destinId")
        if did is None:
            continue  # 跳过 destinId=None 的未归类桶
        tuples.append(
            (
                record_date,
                record_hour,
                source_center_id,
                int(did),
                (r.get("destinName") or "").strip() or None,
                int(dtype) if dtype is not None else None,
                int(r.get("waybillNoTotal") or 0),
                int(r.get("packageNoTotal") or 0),
                start_time,
                end_time,
                now_iso,
            )
        )
    if not tuples:
        return 0
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        _ensure_table(cur)
        cur.executemany(
            f"""
            INSERT INTO {TABLE_NAME}
                (record_date, record_hour, source_center_id, destin_id,
                 destin_name, destin_type, waybill_cnt, package_cnt,
                 start_time, end_time, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(record_date, record_hour, source_center_id, destin_id) DO UPDATE SET
                destin_name = excluded.destin_name,
                destin_type = excluded.destin_type,
                waybill_cnt = excluded.waybill_cnt,
                package_cnt = excluded.package_cnt,
                start_time  = excluded.start_time,
                end_time    = excluded.end_time,
                fetched_at  = excluded.fetched_at
            """,
            tuples,
        )
        conn.commit()
        return len(tuples)
    finally:
        conn.close()


def fetch_center_collect_hour(
    date_str: str,
    hour_int: int,
    *,
    source_center_id: int = DEFAULT_SOURCE_CENTER_ID,
) -> Dict:
    """抓取单个整点小时 [HH:00:00, (HH+1):00:00) 的数据并 UPSERT 入库。"""
    if not (0 <= hour_int <= 23):
        return {"success": False, "error": f"hour_int 越界: {hour_int}"}
    try:
        token = get_gofo_token()
    except Exception as e:
        return {"success": False, "error": f"无 Gofo Token: {e}"}

    start_time = f"{date_str} {hour_int:02d}:00:00"
    if hour_int == 23:
        nd = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime(
            "%Y-%m-%d"
        )
        end_time = f"{nd} 00:00:00"
    else:
        end_time = f"{date_str} {hour_int + 1:02d}:00:00"

    record_hour = f"{hour_int:02d}:00"

    try:
        rows = _call_popover(
            token, start_time, end_time, source_center_id
        )
    except Exception as e:
        return {"success": False, "error": str(e)}

    n = _upsert_rows(
        rows,
        record_date=date_str,
        record_hour=record_hour,
        source_center_id=source_center_id,
        start_time=start_time,
        end_time=end_time,
    )
    centers = sum(1 for r in rows if r.get("destinType") == 1)
    sites = sum(1 for r in rows if r.get("destinType") == 2)
    return {
        "success": True,
        "date": date_str,
        "hour": record_hour,
        "total_rows": len(rows),
        "stored_rows": n,
        "centers": centers,
        "sites": sites,
    }


def fetch_center_collect_day(
    date_str: str,
    upto_hour: Optional[int] = None,
    *,
    source_center_id: int = DEFAULT_SOURCE_CENTER_ID,
    sleep_between: float = 0.2,
) -> Dict:
    """抓取某日 0..upto_hour 各小时；默认：今天截到当前整点，历史日全部 24 小时。"""
    now = datetime.now(BOARD_TZ)
    today_str = now.strftime("%Y-%m-%d")

    if upto_hour is None:
        if date_str == today_str:
            upto_hour = now.hour - 1  # 只抓已经结束的完整小时
            if upto_hour < 0:
                return {
                    "success": True,
                    "date": date_str,
                    "hours_fetched": 0,
                    "stored_rows": 0,
                    "note": "今日还没有完整的整点小时",
                }
        else:
            upto_hour = 23

    total_stored = 0
    hours_ok = 0
    errors: List[str] = []
    for h in range(0, upto_hour + 1):
        res = fetch_center_collect_hour(
            date_str, h, source_center_id=source_center_id
        )
        if res.get("success"):
            hours_ok += 1
            total_stored += int(res.get("stored_rows") or 0)
        else:
            errors.append(f"{date_str} {h:02d}:00 => {res.get('error')}")
        if sleep_between > 0:
            time.sleep(sleep_between)
    out = {
        "success": not errors,
        "date": date_str,
        "hours_fetched": hours_ok,
        "hours_tried": upto_hour + 1,
        "stored_rows": total_stored,
    }
    if errors:
        out["errors"] = errors[:5]
    return out


def fetch_center_collect_backfill(
    days: int = 7,
    *,
    source_center_id: int = DEFAULT_SOURCE_CENTER_ID,
    sleep_between: float = 0.2,
) -> Dict:
    """回补过去 N 天（不含今天就是 N-1 天历史 + 今天到现在）。"""
    days = max(1, min(int(days), 93))
    now = datetime.now(BOARD_TZ)
    today = now.date()
    total_stored = 0
    day_results = []
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
        res = fetch_center_collect_day(
            d,
            source_center_id=source_center_id,
            sleep_between=sleep_between,
        )
        total_stored += int(res.get("stored_rows") or 0)
        day_results.append(res)
    return {
        "success": all(r.get("success") for r in day_results),
        "days": days,
        "total_stored_rows": total_stored,
        "per_day": day_results,
    }


def fetch_latest_completed_hour(
    *,
    source_center_id: int = DEFAULT_SOURCE_CENTER_ID,
) -> Dict:
    """供小时任务调用：抓 LA 时区上一个已完成的整点。"""
    now = datetime.now(BOARD_TZ)
    target = now - timedelta(hours=1)
    return fetch_center_collect_hour(
        target.strftime("%Y-%m-%d"),
        target.hour,
        source_center_id=source_center_id,
    )


if __name__ == "__main__":
    # 手动测试：默认抓今天的所有已完成整点
    today = datetime.now(BOARD_TZ).strftime("%Y-%m-%d")
    print(fetch_center_collect_day(today))
