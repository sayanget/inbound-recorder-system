"""
CNO 直线窄带分拣机（Gofo operatelog）按小时产能同步。

- 数据源：ops/domain/operatelog/selectPageList，与计件拉取相同 scanTypeList=[217]、createDeptId=596。
- 设备名称：CNO直线窄带分拣机-AA/AB/AC/AD → 汇总为生产线 A/B/C/D。
- 时间：洛杉矶整点小时 [HH:00:00, HH:59:59]，与看板/集包同步时区一致。
- 自动任务：与 single_app.gofo_hourly_sync_job 同周期（每整点一次），调用 sync_today_la_hours()
  重拉「今日 LA 从 0 点至今」各小时并 UPSERT 入库。
- 接口限制：单窗命中总条数 >10000 会报错；实际按 env CNO_NARROWBELT_OPERLOG_CHUNK_MINUTES（默认 5）
  分钟切片拉取，仍失败则自动降为 1 分钟、再不行 20 秒。
"""
from __future__ import annotations

import logging
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pytz
import requests

from gofo_config import get_gofo_token

logger = logging.getLogger(__name__)

OPERLOG_URL = (
    "https://dms.gofoexpress.com/prod-api/ops/domain/operatelog/selectPageList"
)
LA_TZ = pytz.timezone(os.environ.get("GOFO_BOARD_TIMEZONE", "America/Los_Angeles"))
CREATE_DEPT_ID = 596
LINE_NAMES = ("A", "B", "C", "D")
OPERATOR_PREFIX = "CNO直线窄带分拣机-"
SUFFIX_TO_LINE = {"AA": "A", "AB": "B", "AC": "C", "AD": "D"}


def narrowbelt_line_from_operator(name: Any) -> Optional[str]:
    if not name or not isinstance(name, str):
        return None
    s = name.strip()
    if OPERATOR_PREFIX not in s:
        return None
    idx = s.rfind("-")
    if idx < 0:
        return None
    suf = "".join(s[idx + 1 :].strip().upper().split())
    return SUFFIX_TO_LINE.get(suf)


def _headers(token: str) -> Dict[str, str]:
    return {
        "Admin-Token": token,
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Connection": "keep-alive",
        "Date-Time-Format": "MM/dd/yyyy HH:mm:ss",
        "Origin": "https://dms.gofoexpress.com",
        "User-Agent": "Mozilla/5.0 (compatible; InboundGofo/1.0)",
        "User-Time-Zone": "America/Los_Angeles",
        "lang": "zh",
        "timeZone": "GMT-0800",
    }


def _is_operlog_overlimit_error(msg: str) -> bool:
    s = str(msg or "")
    return "10000" in s or "不能超过" in s


def _fetch_operatelog_single_window(
    scan_begin: str, scan_end: str, *, max_retries: int = 3
) -> List[Dict[str, Any]]:
    token = get_gofo_token()
    headers = _headers(token)
    all_rows: List[Dict[str, Any]] = []
    page_num = 1
    page_size = 500
    chunk_rows_count = 0
    total = 0
    rows: List[Dict[str, Any]] = []

    while True:
        payload = {
            "containerNoType": "1",
            "createDeptId": CREATE_DEPT_ID,
            "scanBeginTime": scan_begin,
            "scanEndTime": scan_end,
            "scanTypeList": ["217"],
            "pageNum": page_num,
            "pageSize": page_size,
        }
        retry_count = 0
        success = False
        last_err = ""

        while retry_count < max_retries and not success:
            try:
                res = requests.post(
                    OPERLOG_URL, headers=headers, json=payload, timeout=45
                )
                if res.status_code != 200:
                    last_err = f"HTTP {res.status_code}"
                    retry_count += 1
                    time.sleep(2 ** retry_count)
                    continue
                data = res.json()
                if data.get("code") == 401:
                    raise RuntimeError("Gofo API 登录失效 (Token Expired)")
                if data.get("code") != 200:
                    last_err = str(data.get("msg") or data)
                    retry_count += 1
                    time.sleep(2 ** retry_count)
                    continue
                body = data.get("data") or {}
                rows = body.get("records", body.get("list", []))
                total = int(body.get("total") or 0)
                if rows:
                    all_rows.extend(rows)
                    chunk_rows_count += len(rows)
                success = True
            except RuntimeError:
                raise
            except requests.exceptions.Timeout:
                last_err = "timeout"
                retry_count += 1
                time.sleep(2 ** retry_count)
            except Exception as e:
                last_err = str(e)
                retry_count += 1
                time.sleep(2 ** retry_count)

        if not success:
            raise RuntimeError(
                f"operatelog 请求失败 scanBegin={scan_begin} scanEnd={scan_end}: {last_err}"
            )

        if chunk_rows_count >= total or not rows:
            break
        page_num += 1

    return all_rows


def fetch_operatelog_window(
    scan_begin: str, scan_end: str, *, max_retries: int = 3
) -> List[Dict[str, Any]]:
    """
    在 [scan_begin, scan_end] 内按小时间片分批请求，避免单窗 total>10000 被接口拒绝。
    默认每片 5 分钟（env CNO_NARROWBELT_OPERLOG_CHUNK_MINUTES）；失败则对该片降为 1 分钟，再失败降为 20 秒。
    """
    start_dt = LA_TZ.localize(datetime.strptime(scan_begin.strip(), "%Y-%m-%d %H:%M:%S"))
    end_dt = LA_TZ.localize(datetime.strptime(scan_end.strip(), "%Y-%m-%d %H:%M:%S"))
    if end_dt < start_dt:
        return []

    chunk_m = int(os.environ.get("CNO_NARROWBELT_OPERLOG_CHUNK_MINUTES", "5"))
    chunk_m = max(1, min(chunk_m, 60))

    combined: List[Dict[str, Any]] = []
    cur = start_dt
    while cur <= end_dt:
        sub_end = min(cur + timedelta(minutes=chunk_m) - timedelta(seconds=1), end_dt)
        b = cur.strftime("%Y-%m-%d %H:%M:%S")
        e = sub_end.strftime("%Y-%m-%d %H:%M:%S")
        try:
            combined.extend(
                _fetch_operatelog_single_window(b, e, max_retries=max_retries)
            )
        except RuntimeError as ex:
            err_s = str(ex)
            if not _is_operlog_overlimit_error(err_s):
                raise
            if chunk_m > 1:
                logger.info(
                    "cno_narrowbelt operatelog over limit %s–%s, retry with 1-min slices",
                    b,
                    e,
                )
                c2 = cur
                while c2 <= sub_end:
                    e2 = min(c2 + timedelta(minutes=1) - timedelta(seconds=1), sub_end)
                    b2 = c2.strftime("%Y-%m-%d %H:%M:%S")
                    e2s = e2.strftime("%Y-%m-%d %H:%M:%S")
                    try:
                        combined.extend(
                            _fetch_operatelog_single_window(
                                b2, e2s, max_retries=max_retries
                            )
                        )
                    except RuntimeError as ex2:
                        if _is_operlog_overlimit_error(str(ex2)):
                            logger.info(
                                "cno_narrowbelt still over limit %s–%s, use 20s slices",
                                b2,
                                e2s,
                            )
                            c3 = c2
                            while c3 <= e2:
                                e3 = min(
                                    c3 + timedelta(seconds=20) - timedelta(seconds=1),
                                    e2,
                                )
                                combined.extend(
                                    _fetch_operatelog_single_window(
                                        c3.strftime("%Y-%m-%d %H:%M:%S"),
                                        e3.strftime("%Y-%m-%d %H:%M:%S"),
                                        max_retries=max_retries,
                                    )
                                )
                                c3 = e3 + timedelta(seconds=1)
                        else:
                            raise
                    c2 = e2 + timedelta(seconds=1)
            else:
                logger.info(
                    "cno_narrowbelt operatelog over limit %s–%s, use 20s slices (chunk=%s min)",
                    b,
                    e,
                    chunk_m,
                )
                c3 = cur
                while c3 <= sub_end:
                    e3 = min(
                        c3 + timedelta(seconds=20) - timedelta(seconds=1),
                        sub_end,
                    )
                    combined.extend(
                        _fetch_operatelog_single_window(
                            c3.strftime("%Y-%m-%d %H:%M:%S"),
                            e3.strftime("%Y-%m-%d %H:%M:%S"),
                            max_retries=max_retries,
                        )
                    )
                    c3 = e3 + timedelta(seconds=1)
        cur = sub_end + timedelta(seconds=1)

    return combined


def counts_by_production_line(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    """按运单+类型+操作员去重后，按生产线 A-D 计数。"""
    seen = set()
    counts: Dict[str, int] = {k: 0 for k in LINE_NAMES}
    for r in rows:
        op = r.get("createByName")
        line = narrowbelt_line_from_operator(op)
        if not line:
            continue
        waybill = r.get("waybillNo") or ""
        st = r.get("scanTypeStr") or ""
        key = (waybill, st, op)
        if key in seen:
            continue
        seen.add(key)
        counts[line] = counts.get(line, 0) + 1
    return counts


def _persist_rows(
    record_date: str, time_slot: str, counts: Dict[str, int], synced_at: str
) -> None:
    from single_app import get_db

    conn = get_db()
    cur = conn.cursor()
    for line in LINE_NAMES:
        n = int(counts.get(line, 0))
        cur.execute(
            """
            INSERT INTO cno_narrowbelt_hourly
                (record_date, time_slot, line_code, pieces, synced_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(record_date, time_slot, line_code) DO UPDATE SET
                pieces = excluded.pieces,
                synced_at = excluded.synced_at
            """,
            (record_date, time_slot, line, n, synced_at),
        )
    conn.commit()
    conn.close()


def sync_one_la_window(start_la: datetime, end_la: datetime) -> Dict[str, Any]:
    """按任意 [起始, 结束] 时间窗拉取 operatelog；结束可早于整点（用于「当前进行中」小时）。"""
    start_la = start_la.astimezone(LA_TZ)
    end_la = end_la.astimezone(LA_TZ)
    if end_la < start_la:
        return {
            "success": True,
            "skipped": True,
            "record_date": start_la.strftime("%Y-%m-%d"),
            "time_slot": start_la.strftime("%H:00"),
            "counts": {k: 0 for k in LINE_NAMES},
            "raw_rows": 0,
        }

    begin_str = start_la.strftime("%Y-%m-%d %H:%M:%S")
    end_str = end_la.strftime("%Y-%m-%d %H:%M:%S")
    record_date = start_la.strftime("%Y-%m-%d")
    time_slot = start_la.strftime("%H:00")
    synced_at = datetime.now(LA_TZ).strftime("%Y-%m-%d %H:%M:%S")

    rows = fetch_operatelog_window(begin_str, end_str)
    counts = counts_by_production_line(rows)
    _persist_rows(record_date, time_slot, counts, synced_at)
    return {
        "success": True,
        "record_date": record_date,
        "time_slot": time_slot,
        "counts": counts,
        "raw_rows": len(rows),
    }


def sync_one_la_hour(slot_start_la: datetime) -> Dict[str, Any]:
    """同步洛杉矶时区下一整点小时的数据。"""
    if slot_start_la.tzinfo is None:
        slot_start_la = LA_TZ.localize(slot_start_la)
    else:
        slot_start_la = slot_start_la.astimezone(LA_TZ)
    end_la = slot_start_la + timedelta(hours=1) - timedelta(seconds=1)
    return sync_one_la_window(slot_start_la, end_la)


def sync_la_calendar_day_hours(record_date_str: str) -> Dict[str, Any]:
    """
    拉取指定洛杉矶日历日从 00:00 起的每个整点小时。
    - 当天：截止到当前时刻；已结束小时为整窗，进行中小时为 [HH:00, now]。
    - 过往日期：拉满该 LA 日历日留在表上的 24 个整点（不截断到「此刻」）。
    """
    record_date_str = (record_date_str or "").strip()[:10]
    d = datetime.strptime(record_date_str, "%Y-%m-%d").date()
    day_start = LA_TZ.localize(datetime(d.year, d.month, d.day, 0, 0, 0))
    now = datetime.now(LA_TZ)
    today_la = now.date()

    if d > today_la:
        return {
            "success": False,
            "error": "不能拉取未来日期",
            "date": record_date_str,
            "hours_attempted": 0,
            "errors": [],
            "detail": [],
        }

    end_cap: Optional[datetime] = None if d < today_la else now
    detail: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    for h in range(24):
        slot = day_start + timedelta(hours=h)
        if slot.strftime("%Y-%m-%d") != record_date_str:
            break
        natural_end = slot + timedelta(hours=1) - timedelta(seconds=1)
        if end_cap is not None:
            if slot > end_cap:
                break
            slot_end = min(natural_end, end_cap)
        else:
            slot_end = natural_end
        try:
            detail.append(sync_one_la_window(slot, slot_end))
        except Exception as e:
            errors.append({"slot": slot.isoformat(), "error": str(e)})
            logger.warning("cno_narrowbelt sync hour failed: %s", e)

    return {
        "success": len(errors) == 0,
        "date": record_date_str,
        "hours_attempted": len(detail),
        "errors": errors,
        "detail": detail,
    }


def sync_today_la_hours() -> Dict[str, Any]:
    """拉取「今天」（洛杉矶）0 点以来各小时。"""
    return sync_la_calendar_day_hours(datetime.now(LA_TZ).strftime("%Y-%m-%d"))


def sync_lookback_hours(lookback: Optional[int] = None) -> Dict[str, Any]:
    """
    自当前整点起向前回刷若干完整小时（默认 env CNO_NARROWBELT_LOOKBACK_HOURS 或 6）。
    在每小时定时任务中调用一次即可逐步覆盖昨日及修正最近几小时。
    """
    if lookback is None:
        lookback = int(os.environ.get("CNO_NARROWBELT_LOOKBACK_HOURS", "6"))
    lookback = max(1, min(lookback, 72))

    now = datetime.now(LA_TZ)
    floor = now.replace(minute=0, second=0, microsecond=0)
    detail = []
    errors = []
    for i in range(1, lookback + 1):
        slot_start = floor - timedelta(hours=i)
        try:
            r = sync_one_la_hour(slot_start)
            detail.append(r)
        except Exception as e:
            errors.append({"slot": slot_start.isoformat(), "error": str(e)})
            logger.warning("cno_narrowbelt sync hour failed: %s", e)

    return {
        "success": len(errors) == 0,
        "lookback": lookback,
        "hours_ok": len(detail),
        "errors": errors,
        "detail": detail,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    day = (
        sys.argv[1].strip()
        if len(sys.argv) > 1
        else datetime.now(LA_TZ).strftime("%Y-%m-%d")
    )
    day = day[:10]
    out = sync_la_calendar_day_hours(day)
    print(
        out.get("success"),
        out.get("date"),
        "hours=",
        out.get("hours_attempted"),
        "errors=",
        len(out.get("errors") or []),
    )
    for e in out.get("errors") or []:
        print(" ERR:", e)
