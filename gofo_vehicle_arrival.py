# Copyright (c) 2026 Fan Yang. All rights reserved.
"""GoFO 中心看板「到车情况 · 当日已到」— transport/arrive/car/popover。"""
from __future__ import annotations

import os
import re
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

import pytz
import requests

from gofo_config import get_gofo_token

LA_TZ = pytz.timezone(os.environ.get("GOFO_BOARD_TIMEZONE", "America/Los_Angeles"))
ARRIVE_POPOVER_URL = (
    "https://dms.gofoexpress.com/prod-api/dbu_report/common/center/transport/arrive/car/popover"
)
LOAD_BAG_POPOVER_URL = (
    "https://dms.gofoexpress.com/prod-api/dbu_report/common/center/transport/load/bag/total/popover"
)
CENTER_PACK_DETAIL_URL = "https://dms.gofoexpress.com/prod-api/ops/centerPack/detail"
WAYBILL_TRACK_URL = "https://dms.gofoexpress.com/prod-api/waybill/track/list/private"
DEFAULT_CENTER_ID = int(os.environ.get("GOFO_CENTER_ID", "596"))
TRACK_BATCH_SIZE = int(os.environ.get("GOFO_TRACK_BATCH_SIZE", "30"))
# arrive2 = 看板「到车情况 · 当日已到」弹窗
ARRIVED_TODAY_DATE_TYPE = os.environ.get("GOFO_ARRIVAL_DATE_TYPE", "arrive2").strip() or "arrive2"
DESTINATION_FILTER = os.environ.get("GOFO_CNO_H_DESTINATION_NAME", "CNO.H").strip()
CNO_SIGNIN_MARKER = os.environ.get(
    "GOFO_CNO_SIGNIN_MARKER", "Signed in at sorting center CNO.H"
).strip()
CNO_REPACKED_EMPTY_NOTE = os.environ.get(
    "GOFO_CNO_REPACKED_EMPTY_NOTE", "已签入分拣重新集包（袋内无运单）"
).strip()
LATE_CNO_SIGNIN_MINUTES = int(os.environ.get("GOFO_LATE_CNO_SIGNIN_MINUTES", "30"))
TRIP_ARRIVAL_MATCH_MINUTES = int(os.environ.get("GOFO_TRIP_ARRIVAL_MATCH_MINUTES", "5"))


def _cno_signed_markers() -> List[str]:
    """抵达后视为 CNO.H 已签入（含离分拣：签入→集包后才离站，仅作已签入判定，不作签入时刻）。"""
    raw = os.environ.get("GOFO_CNO_SIGNED_MARKERS", "").strip()
    if raw:
        return [m.strip() for m in raw.split("|") if m.strip()]
    return [
        CNO_SIGNIN_MARKER,
        "Left sorting center CNO.H",
    ]


def _context_matches_cno_signed(ctx: str) -> bool:
    text = str(ctx or "")
    return any(marker in text for marker in _cno_signed_markers())


def _context_matches_cno_signin_time(ctx: str) -> bool:
    """仅分拣签入节点，用于卸车用时；不含离分拣。"""
    text = str(ctx or "")
    marker = CNO_SIGNIN_MARKER
    return bool(marker) and marker in text


UNLOAD_WARN_SECONDS = int(os.environ.get("GOFO_UNLOAD_WARN_SEC", str(45 * 60)))
UNLOAD_TIMELY_SECONDS = int(os.environ.get("GOFO_UNLOAD_TIMELY_SEC", str(UNLOAD_WARN_SECONDS)))
UNLOAD_OVERTIME_SECONDS = int(os.environ.get("GOFO_UNLOAD_OVERTIME_SEC", str(UNLOAD_WARN_SECONDS)))
MAX_POPOVER_PAGES = int(os.environ.get("GOFO_ARRIVAL_MAX_PAGES", "30"))
POPOVER_PAGE_SIZE = int(os.environ.get("GOFO_ARRIVAL_PAGE_SIZE", "200"))
BAG_PAGE_SIZE = int(os.environ.get("GOFO_BAG_PAGE_SIZE", "200"))
PACK_WAYBILL_PAGE_SIZE = int(os.environ.get("GOFO_PACK_WAYBILL_PAGE_SIZE", "200"))


def _popover_headers(token: str) -> Dict[str, str]:
    return {
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {token}",
        "Admin-Token": token,
        "Content-Type": "application/json",
        "Channel-Id": "us",
        "User-Time-Zone": "America/Los_Angeles",
        "timeZone": "GMT-0700",
        "Date-Time-Format": "MM/dd/yyyy HH:mm:ss",
        "lang": "zh",
        "Origin": "https://dms.gofoexpress.com",
        "Referer": "https://dms.gofoexpress.com/gofo-report/report/reportCenter/centerViewingBoard",
    }


def _parse_la_dt(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() == "null":
        return None
    if s.endswith("Z"):
        s = s[:-1].strip()
    if "T" in s:
        s = s.replace("T", " ", 1)
    if "." in s and " " in s:
        s = s.split(".")[0].strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            naive = datetime.strptime(s[:19] if len(s) > 19 else s, fmt)
            return LA_TZ.localize(naive)
        except ValueError:
            continue
    m = re.search(r"(\d{1,2}:\d{2}:\d{2}).*?(\d{1,2}/\d{1,2}/\d{4})", s)
    if m:
        time_part, date_part = m.group(1), m.group(2)
        for fmt in ("%d/%m/%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S"):
            try:
                naive = datetime.strptime(f"{date_part} {time_part}", fmt)
                return LA_TZ.localize(naive)
            except ValueError:
                continue
    return None


def _parse_operation_time(val: Any) -> Optional[datetime]:
    return _parse_la_dt(val)


def _fmt_duration(delta: timedelta) -> str:
    secs = int(delta.total_seconds())
    sign = ""
    if secs < 0:
        sign = "-"
        secs = abs(secs)
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{sign}{h}小时{m}分"
    if m > 0:
        return f"{sign}{m}分{s}秒"
    return f"{sign}{s}秒"


def _fmt_dt(val: Any) -> str:
    dt = _parse_la_dt(val) if not isinstance(val, datetime) else val
    if dt is None:
        return str(val).strip() if val not in (None, "") else ""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _int_field(val: Any) -> int:
    try:
        if val is None or str(val).strip() == "":
            return 0
        return int(val)
    except (TypeError, ValueError):
        return 0


def _normalize_popover_row(rec: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "task_no": str(rec.get("taskNo") or "").strip(),
        "place_of_origin": str(rec.get("placeOfOrigin") or "").strip(),
        "destination": str(rec.get("destination") or "").strip(),
        "actual_departure_time": _fmt_dt(rec.get("reportActualDepartureTime")),
        "actual_arrival_time": _fmt_dt(rec.get("reportActualArrivalTime")),
        "transit_boxes_total": _int_field(rec.get("loadBagTotal")),
        "waybill_total": _int_field(rec.get("loadWaybillTotal")),
        "line_name": str(rec.get("sendCarRoad") or "").strip(),
        "license_plate_no": str(rec.get("licensePlateNo") or "").strip(),
        "task_status_str": str(rec.get("vehicleStatus") or "").strip(),
        "task_arrival_id": rec.get("taskArrivalId"),
    }


def _fetch_popover_page(
    page_num: int,
    page_size: int,
    *,
    date_type: str = ARRIVED_TODAY_DATE_TYPE,
    center_id: int = DEFAULT_CENTER_ID,
    token: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    token = token or get_gofo_token()
    payload = {
        "dateType": date_type,
        "centerIds": [center_id],
        "pageNum": page_num,
        "pageSize": page_size,
    }
    res = requests.post(
        ARRIVE_POPOVER_URL,
        headers=_popover_headers(token),
        json=payload,
        timeout=45,
    )
    res.raise_for_status()
    body = res.json()
    if body.get("code") == 401:
        raise RuntimeError("Gofo Token 失效（401）")
    if body.get("code") not in (200, 0, None) and str(body.get("code")) != "200":
        raise RuntimeError(body.get("msg") or body.get("message") or f"popover code={body.get('code')}")
    data = body.get("data") or {}
    recs = data.get("records") or data.get("list") or data.get("rows") or []
    if not isinstance(recs, list):
        recs = []
    try:
        total = int(data.get("total") if data.get("total") is not None else len(recs))
    except (TypeError, ValueError):
        total = len(recs)
    return recs, total


def fetch_arrival_popover_rows(
    *,
    date_type: str = ARRIVED_TODAY_DATE_TYPE,
    center_id: int = DEFAULT_CENTER_ID,
    destination_name: str = DESTINATION_FILTER,
    token: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """拉取看板 popover 全部分页；返回 (明细行, API total)。"""
    matched: List[Dict[str, Any]] = []
    seen: set = set()

    for page in range(1, MAX_POPOVER_PAGES + 1):
        recs, _total = _fetch_popover_page(
            page, POPOVER_PAGE_SIZE, date_type=date_type, center_id=center_id, token=token
        )

        if not recs:
            break

        for rec in recs:
            if not isinstance(rec, dict):
                continue
            dest = str(rec.get("destination") or "").strip()
            if destination_name and dest and dest != destination_name:
                continue
            key = rec.get("taskArrivalId") or rec.get("taskNo")
            if key is None or key in seen:
                continue
            seen.add(key)
            row = _normalize_popover_row(rec)
            if not row["task_no"]:
                continue
            matched.append(row)

        if len(recs) < POPOVER_PAGE_SIZE:
            break

    matched.sort(key=lambda r: r.get("actual_arrival_time") or "", reverse=True)
    return matched, len(matched)


def fetch_arrival_details() -> Dict[str, Any]:
    rows, _ = fetch_arrival_popover_rows()
    now_la = datetime.now(LA_TZ)
    return {
        "arrived_today": len(rows),
        "destination": DESTINATION_FILTER or "CNO.H",
        "date_type": ARRIVED_TODAY_DATE_TYPE,
        "center_id": DEFAULT_CENTER_ID,
        "fetched_at": now_la.strftime("%Y-%m-%d %H:%M:%S"),
        "rows": rows,
        "total": len(rows),
    }


def fetch_arrival_summary() -> Dict[str, Any]:
    _, total = _fetch_popover_page(1, max(10, POPOVER_PAGE_SIZE))
    now_la = datetime.now(LA_TZ)
    return {
        "arrived_today": total,
        "destination": DESTINATION_FILTER or "CNO.H",
        "date_type": ARRIVED_TODAY_DATE_TYPE,
        "center_id": DEFAULT_CENTER_ID,
        "fetched_at": now_la.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _fetch_load_bag_page(
    task_no: str,
    task_arrival_id: int,
    page_num: int,
    page_size: int,
    *,
    token: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    token = token or get_gofo_token()
    payload = {
        "taskNo": task_no,
        "taskArrivalId": int(task_arrival_id),
        "pageNum": page_num,
        "pageSize": page_size,
    }
    res = requests.post(
        LOAD_BAG_POPOVER_URL,
        headers=_popover_headers(token),
        json=payload,
        timeout=45,
    )
    res.raise_for_status()
    body = res.json()
    if body.get("code") == 401:
        raise RuntimeError("Gofo Token 失效（401）")
    if body.get("code") not in (200, 0, None) and str(body.get("code")) != "200":
        raise RuntimeError(body.get("msg") or body.get("message") or f"bag popover code={body.get('code')}")
    data = body.get("data") or {}
    recs = data.get("records") or data.get("list") or data.get("rows") or []
    if not isinstance(recs, list):
        recs = []
    try:
        total = int(data.get("total") if data.get("total") is not None else len(recs))
    except (TypeError, ValueError):
        total = len(recs)
    return recs, total


def _normalize_bag_row(rec: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "serial_number": str(rec.get("serialNumber") or "").strip(),
        "load_scan_time": _fmt_dt(rec.get("loadScanTime")),
        "scan_type": str(rec.get("scanTypeStr") or "").strip(),
        "load_point": str(rec.get("actualLoadMeridianStopPoint") or "").strip(),
        "plan_unload_point": str(rec.get("planUnLoadMeridianStopPoint") or "").strip(),
        "unload_point": str(rec.get("actualUnLoadMeridianStopPoint") or "").strip(),
        "unload_scan_time": _fmt_dt(rec.get("unLoadScanTime")),
    }


def fetch_load_bag_details(
    task_no: str,
    task_arrival_id: int,
    *,
    enrich_tracks: bool = False,
) -> Dict[str, Any]:
    """装车箱数钻取：袋牌号列表（load/bag/total/popover）。"""
    task_no = (task_no or "").strip()
    if not task_no:
        raise ValueError("缺少 taskNo")
    try:
        arrival_id = int(task_arrival_id)
    except (TypeError, ValueError):
        raise ValueError("缺少或无效 taskArrivalId")

    rows: List[Dict[str, Any]] = []
    seen: set = set()
    api_total = 0

    for page in range(1, MAX_POPOVER_PAGES + 1):
        recs, total = _fetch_load_bag_page(task_no, arrival_id, page, BAG_PAGE_SIZE)
        if page == 1:
            api_total = total
        if not recs:
            break
        for rec in recs:
            if not isinstance(rec, dict):
                continue
            row = _normalize_bag_row(rec)
            sn = row["serial_number"]
            if not sn or sn in seen:
                continue
            seen.add(sn)
            rows.append(row)
        if len(recs) < BAG_PAGE_SIZE:
            break

    if enrich_tracks:
        _enrich_bags_with_tracks(rows)

    now_la = datetime.now(LA_TZ)
    return {
        "task_no": task_no,
        "task_arrival_id": arrival_id,
        "total": api_total if api_total > 0 else len(rows),
        "rows": rows,
        "fetched_at": now_la.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _fetch_center_pack_page(
    package_no: str,
    page_num: int,
    page_size: int,
    *,
    token: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    token = token or get_gofo_token()
    payload = {
        "pageNum": page_num,
        "pageSize": page_size,
        "packageNo": package_no,
    }
    res = requests.post(
        CENTER_PACK_DETAIL_URL,
        headers=_popover_headers(token),
        json=payload,
        timeout=45,
    )
    res.raise_for_status()
    body = res.json()
    if body.get("code") == 401:
        raise RuntimeError("Gofo Token 失效（401）")
    if body.get("code") not in (200, 0, None) and str(body.get("code")) != "200":
        raise RuntimeError(body.get("msg") or body.get("message") or f"centerPack code={body.get('code')}")
    data = body.get("data") or {}
    recs = data.get("records") or data.get("list") or data.get("rows") or []
    if not isinstance(recs, list):
        recs = []
    try:
        total = int(data.get("total") if data.get("total") is not None else len(recs))
    except (TypeError, ValueError):
        total = len(recs)
    return recs, total


def _normalize_waybill_row(rec: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "waybill_no": str(rec.get("waybillNo") or "").strip(),
        "to_code": str(rec.get("toCode") or "").strip(),
        "to_state": str(rec.get("toState") or "").strip(),
        "to_city": str(rec.get("toCity") or "").strip(),
        "package_no": str(rec.get("packageNo") or "").strip(),
    }


def fetch_package_waybill_details(
    package_no: str,
    *,
    actual_arrival_time: Optional[str] = None,
) -> Dict[str, Any]:
    """袋牌号钻取：集包内运单号（ops/centerPack/detail）。"""
    package_no = (package_no or "").strip()
    if not package_no:
        raise ValueError("缺少 packageNo")

    rows: List[Dict[str, Any]] = []
    seen: set = set()
    api_total = 0

    for page in range(1, MAX_POPOVER_PAGES + 1):
        recs, total = _fetch_center_pack_page(package_no, page, PACK_WAYBILL_PAGE_SIZE)
        if page == 1:
            api_total = total
        if not recs:
            break
        for rec in recs:
            if not isinstance(rec, dict):
                continue
            row = _normalize_waybill_row(rec)
            wb = row["waybill_no"]
            if not wb or wb in seen:
                continue
            seen.add(wb)
            rows.append(row)
        if len(recs) < PACK_WAYBILL_PAGE_SIZE:
            break

    arr_dt = _parse_la_dt(actual_arrival_time) if actual_arrival_time else None
    if arr_dt and rows:
        order_nos = [str(r.get("waybill_no") or "").strip() for r in rows if r.get("waybill_no")]
        signins = fetch_waybill_signin_events_batch(
            order_nos, after_dt=arr_dt, trip_arrival_dt=arr_dt
        )
        for row in rows:
            wb = str(row.get("waybill_no") or "").strip()
            ev = signins.get(wb)
            if ev:
                row["es_context"] = ev.get("es_context", "")
                row["operation_time"] = _fmt_dt(ev.get("operation_time", ""))
            else:
                row["es_context"] = ""
                row["operation_time"] = ""
    else:
        _attach_tracks_to_rows(rows, key_field="waybill_no")

    now_la = datetime.now(LA_TZ)
    return {
        "package_no": package_no,
        "total": api_total if api_total > 0 else len(rows),
        "rows": rows,
        "fetched_at": now_la.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _extract_waybill_no_from_track_item(item: Dict[str, Any]) -> str:
    wb = item.get("waybill")
    if isinstance(wb, dict):
        for k in ("waybillNo", "orderNo", "waybill_no"):
            v = wb.get(k)
            if v:
                return str(v).strip()
    for k in ("waybillNo", "orderNo", "order_no"):
        v = item.get(k)
        if v:
            return str(v).strip()
    return ""


def _normalize_track_event(ev: Dict[str, Any]) -> Dict[str, str]:
    return {
        "es_context": str(ev.get("es_context") or ev.get("esContext") or "").strip(),
        "operation_time": str(ev.get("operationTime") or ev.get("operation_time") or "").strip(),
    }


def _newest_track_from_item(item: Dict[str, Any]) -> Dict[str, str]:
    """取轨迹 list 中 operationTime 最新的一条（无法解析时间时退回 list[0]）。"""
    lst = item.get("list") or []
    best: Optional[Tuple[Dict[str, str], datetime]] = None
    fallback: Optional[Dict[str, str]] = None
    for ev in lst:
        if not isinstance(ev, dict):
            continue
        norm = _normalize_track_event(ev)
        if fallback is None:
            fallback = norm
        dt = _parse_operation_time(norm.get("operation_time", ""))
        if not dt:
            continue
        if best is None or dt > best[1]:
            best = (norm, dt)
    if best:
        return best[0]
    return fallback or {"es_context": "", "operation_time": ""}


def _latest_track_from_item(item: Dict[str, Any]) -> Dict[str, str]:
    return _newest_track_from_item(item)


def _fetch_waybill_track_batch(
    order_nos: List[str],
    *,
    token: Optional[str] = None,
) -> List[Dict[str, Any]]:
    token = token or get_gofo_token()
    payload = {
        "orderNos": order_nos,
        "queryType": "1",
        "delStatus": "0",
    }
    res = requests.post(
        WAYBILL_TRACK_URL,
        headers=_popover_headers(token),
        json=payload,
        timeout=60,
    )
    res.raise_for_status()
    body = res.json()
    if body.get("code") == 401:
        raise RuntimeError("Gofo Token 失效（401）")
    if body.get("code") not in (200, 0, None) and str(body.get("code")) != "200":
        raise RuntimeError(body.get("msg") or body.get("message") or f"waybill track code={body.get('code')}")
    data = body.get("data")
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        inner = data.get("list") or data.get("records") or data.get("rows") or []
        if isinstance(inner, list):
            return [x for x in inner if isinstance(x, dict)]
    return []


def _find_earliest_event_in_item(
    item: Dict[str, Any],
    *,
    after_dt: Optional[datetime] = None,
    matcher,
) -> Optional[Tuple[Dict[str, str], datetime]]:
    lst = item.get("list") or []
    best: Optional[Tuple[Dict[str, str], datetime]] = None
    for ev in lst:
        if not isinstance(ev, dict):
            continue
        ctx = str(ev.get("es_context") or ev.get("esContext") or "")
        if not matcher(ctx):
            continue
        norm = _normalize_track_event(ev)
        dt = _parse_operation_time(norm.get("operation_time", ""))
        if not dt:
            continue
        if after_dt is not None and dt < after_dt:
            continue
        if best is None or dt < best[1]:
            best = (norm, dt)
    return best


def _find_cno_signed_event_in_item(
    item: Dict[str, Any],
    after_dt: Optional[datetime] = None,
) -> Optional[Tuple[Dict[str, str], datetime]]:
    """抵达后是否已有 CNO.H 签入/离分拣（判定已签入）。"""
    return _find_earliest_event_in_item(
        item, after_dt=after_dt, matcher=_context_matches_cno_signed
    )


def _find_cno_signin_time_event_in_item(
    item: Dict[str, Any],
    after_dt: Optional[datetime] = None,
) -> Optional[Tuple[Dict[str, str], datetime]]:
    """抵达后最早分拣签入时刻（不含离分拣）。"""
    return _find_earliest_event_in_item(
        item, after_dt=after_dt, matcher=_context_matches_cno_signin_time
    )


def _resolve_waybill_cno_signin_from_item(
    item: Dict[str, Any],
    *,
    after_dt: Optional[datetime] = None,
    trip_arrival_dt: Optional[datetime] = None,
) -> Optional[Dict[str, str]]:
    """已签入判定 + 卸车签入时刻（离分拣不算签入时刻）。"""
    signed_hit = _find_cno_signed_event_in_item(item, after_dt=after_dt)
    if not signed_hit:
        return None
    signed_ev, _ = signed_hit
    time_hit = _find_cno_signin_time_event_in_item(item, after_dt=after_dt)
    vehicle_hit = _find_vehicle_arrival_cno_in_item(item, after_dt=after_dt)
    trip_tolerance = timedelta(minutes=max(1, TRIP_ARRIVAL_MATCH_MINUTES))

    if time_hit:
        time_ev, signin_dt = time_hit
        adj_ev, adj_dt = _coalesce_delayed_cno_signin(
            time_ev, signin_dt, vehicle_hit, trip_arrival_dt
        )
        return {**adj_ev, "operation_time": _fmt_dt(adj_dt)}

    if vehicle_hit:
        veh_ev, veh_dt = vehicle_hit
        if trip_arrival_dt is None or abs(veh_dt - trip_arrival_dt) <= trip_tolerance:
            return {
                "es_context": signed_ev.get("es_context", veh_ev.get("es_context", "")),
                "operation_time": _fmt_dt(veh_dt),
            }

    # 仅有离分拣等、无分拣签入时刻：计为已签入，但不以离分拣时间作签入时刻
    return {
        "es_context": signed_ev.get("es_context", ""),
        "operation_time": "",
    }


def _find_signin_event_in_item(
    item: Dict[str, Any],
    marker: str = CNO_SIGNIN_MARKER,
    after_dt: Optional[datetime] = None,
) -> Optional[Dict[str, str]]:
    """取轨迹中 CNO.H 签入/离分拣；若提供 after_dt 则只认不早于该时刻的事件。"""
    lst = item.get("list") or []
    best: Optional[Tuple[Dict[str, str], datetime]] = None
    for ev in lst:
        if not isinstance(ev, dict):
            continue
        ctx = str(ev.get("es_context") or ev.get("esContext") or "")
        if marker:
            if marker not in ctx and not _context_matches_cno_signed(ctx):
                continue
        elif not _context_matches_cno_signed(ctx):
            continue
        norm = _normalize_track_event(ev)
        dt = _parse_operation_time(norm.get("operation_time", ""))
        if not dt:
            continue
        if after_dt is not None and dt < after_dt:
            continue
        if best is None or dt < best[1]:
            best = (norm, dt)
    return best[0] if best else None


def _find_vehicle_arrival_cno_in_item(
    item: Dict[str, Any],
    *,
    after_dt: Optional[datetime] = None,
) -> Optional[Tuple[Dict[str, str], datetime]]:
    """取轨迹中车辆抵达 CNO.H 的最早节点（用于修正晚到的重复签入扫描）。"""
    dest = (DESTINATION_FILTER or "CNO.H").strip()
    arrived_needle = f"arrived at {dest}"
    lst = item.get("list") or []
    best: Optional[Tuple[Dict[str, str], datetime]] = None
    for ev in lst:
        if not isinstance(ev, dict):
            continue
        ctx = str(ev.get("es_context") or ev.get("esContext") or "")
        low = ctx.lower()
        if arrived_needle.lower() not in low or "vehicle" not in low:
            continue
        norm = _normalize_track_event(ev)
        dt = _parse_operation_time(norm.get("operation_time", ""))
        if not dt:
            continue
        if after_dt is not None and dt < after_dt:
            continue
        if best is None or dt < best[1]:
            best = (norm, dt)
    return best


def _coalesce_delayed_cno_signin(
    signin_ev: Dict[str, str],
    signin_dt: datetime,
    vehicle_hit: Optional[Tuple[Dict[str, str], datetime]],
    trip_arrival_dt: Optional[datetime],
) -> Tuple[Dict[str, str], datetime]:
    """若分拣签入远晚于同票到车，且到车时刻贴近车次到货，则以到车时刻作为本车签入。"""
    if not vehicle_hit or not trip_arrival_dt:
        return signin_ev, signin_dt
    vehicle_ev, vehicle_dt = vehicle_hit
    late_threshold = timedelta(minutes=max(1, LATE_CNO_SIGNIN_MINUTES))
    trip_tolerance = timedelta(minutes=max(1, TRIP_ARRIVAL_MATCH_MINUTES))
    if signin_dt - vehicle_dt < late_threshold:
        return signin_ev, signin_dt
    if abs(vehicle_dt - trip_arrival_dt) > trip_tolerance:
        return signin_ev, signin_dt
    return signin_ev, vehicle_dt


def fetch_waybill_signin_events_batch(
    order_nos: List[str],
    *,
    marker: str = CNO_SIGNIN_MARKER,
    after_dt: Optional[datetime] = None,
    trip_arrival_dt: Optional[datetime] = None,
) -> Dict[str, Dict[str, str]]:
    """批量查询运单轨迹中 CNO.H 签入（默认取抵达后最早一条，排除更早的历史签入）。"""
    unique = []
    seen: set = set()
    for raw in order_nos or []:
        no = str(raw or "").strip()
        if not no or no in seen:
            continue
        seen.add(no)
        unique.append(no)
    if not unique:
        return {}

    out: Dict[str, Dict[str, str]] = {}
    token = get_gofo_token()
    for i in range(0, len(unique), TRACK_BATCH_SIZE):
        chunk = unique[i : i + TRACK_BATCH_SIZE]
        items = _fetch_waybill_track_batch(chunk, token=token)
        for item in items:
            wb = _extract_waybill_no_from_track_item(item)
            if not wb:
                continue
            ev = _resolve_waybill_cno_signin_from_item(
                item, after_dt=after_dt, trip_arrival_dt=trip_arrival_dt
            )
            if ev:
                out[wb] = ev
    return out


def _earliest_signin_among_waybills(
    waybills: List[str],
    signins: Dict[str, Dict[str, str]],
) -> Optional[Tuple[str, Dict[str, str], datetime]]:
    """袋内多票：取抵达后最早签入（代表该箱签入时刻）。"""
    best: Optional[Tuple[str, Dict[str, str], datetime]] = None
    for wb in waybills or []:
        ev = signins.get(wb)
        if not ev:
            continue
        dt = _parse_operation_time(ev.get("operation_time", ""))
        if not dt:
            continue
        if best is None or dt < best[2]:
            best = (wb, ev, dt)
    return best


def is_cno_plan_unload_point(plan_unload_point: Any) -> bool:
    pt = str(plan_unload_point or "").strip()
    target = (DESTINATION_FILTER or "CNO.H").strip()
    return bool(pt) and pt == target


def is_return_bag(serial_number: Any) -> bool:
    """袋牌号 R 开头为退件，不参与 CNO.H 签入状态验证。"""
    serial = str(serial_number or "").strip()
    return bool(serial) and serial.upper().startswith("R")


def filter_cno_plan_unload_bags(bags: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [b for b in bags if is_cno_plan_unload_point(b.get("plan_unload_point"))]


def filter_signin_eligible_bags(bags: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """CNO.H 计划卸车袋牌中，排除退件（R 开头）后参与签入统计的箱。"""
    return [
        b
        for b in filter_cno_plan_unload_bags(bags)
        if not is_return_bag(b.get("serial_number"))
    ]


def count_cno_plan_unload_bags(bags: List[Dict[str, Any]]) -> int:
    return len(filter_signin_eligible_bags(bags))


def apply_trip_bag_metrics(trip: Dict[str, Any], bag_rows: List[Dict[str, Any]]) -> None:
    """按计划卸车点 CNO.H 筛选袋牌（退件 R 开头不计入签入）；签入指标看袋内运单轨迹是否曾出现 CNO.H 签入。"""
    cno_bags = filter_signin_eligible_bags(bag_rows)
    trip["transit_boxes_total"] = len(cno_bags)
    arrival = trip.get("actual_arrival_time") or ""
    signin_map = _compute_cno_bag_signin_map(cno_bags, arrival)
    annotate_bags_signin_status(bag_rows, signin_map)
    trip.update(_signin_summary_from_signin_map(signin_map, len(cno_bags), arrival))


def _compute_cno_bag_signin_map(
    cno_bags: List[Dict[str, Any]],
    actual_arrival_time: str,
) -> Dict[str, Dict[str, Any]]:
    """每袋 CNO.H 箱：是否抵达后有签入，及样本运单/轨迹。"""
    out: Dict[str, Dict[str, Any]] = {}
    if not cno_bags:
        return out

    arr_dt = _parse_la_dt(actual_arrival_time)
    serials = [
        str(b.get("serial_number") or "").strip()
        for b in cno_bags
        if str(b.get("serial_number") or "").strip()
    ]
    if not serials:
        return out

    pkg_to_wbs = _first_page_waybills_for_packages(serials)
    all_wbs = [wb for wbs in pkg_to_wbs.values() for wb in wbs]
    signins = (
        fetch_waybill_signin_events_batch(all_wbs, after_dt=arr_dt, trip_arrival_dt=arr_dt)
        if all_wbs
        else {}
    )

    for bag in cno_bags:
        pkg = str(bag.get("serial_number") or "").strip()
        if not pkg:
            continue
        wbs = pkg_to_wbs.get(pkg) or []
        # 袋内已无运单：通常已签入并重新集包，不计为未签入
        if not wbs:
            out[pkg] = {
                "cno_signed": 1,
                "sample_waybill_no": "",
                "es_context": CNO_REPACKED_EMPTY_NOTE,
                "operation_time": "",
            }
            continue
        hit = _earliest_signin_among_waybills(wbs, signins)
        signed = bool(not wbs or any(wb in signins for wb in wbs))
        if signed:
            wb, ev, dt = hit if hit else ("", {}, None)
            out[pkg] = {
                "cno_signed": 1,
                "sample_waybill_no": wb or (wbs[0] if wbs else ""),
                "es_context": (ev.get("es_context", "") if ev else ""),
                "operation_time": _fmt_dt(dt) if dt else "",
            }
        else:
            out[pkg] = {
                "cno_signed": 0,
                "sample_waybill_no": wbs[0] if wbs else "",
                "es_context": "",
                "operation_time": "",
            }
    return out


def trip_signin_counts_from_bags(bag_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """按可签入袋牌（CNO.H、非 R 退件）汇总箱数与签入数。"""
    eligible = filter_signin_eligible_bags(bag_rows or [])
    boxes = len(eligible)
    signed = sum(1 for b in eligible if int(b.get("cno_signed") or 0) == 1)
    return {
        "transit_boxes_total": boxes,
        "cno_signed_bag_count": signed,
        "bags_incomplete": boxes > 0 and signed < boxes,
    }


def annotate_bags_signin_status(
    bag_rows: List[Dict[str, Any]],
    signin_map: Dict[str, Dict[str, Any]],
) -> None:
    """把签入结果写回袋牌行（同步入库 / 页面展示）。"""
    for bag in bag_rows or []:
        pkg = str(bag.get("serial_number") or "").strip()
        if not is_cno_plan_unload_point(bag.get("plan_unload_point")):
            bag["cno_signed"] = None
            continue
        if is_return_bag(pkg):
            bag["cno_signed"] = None
            bag["is_return"] = True
            continue
        info = signin_map.get(pkg) or {"cno_signed": 0, "es_context": "", "operation_time": ""}
        bag["cno_signed"] = int(info.get("cno_signed") or 0)
        if info.get("sample_waybill_no"):
            bag["sample_waybill_no"] = info["sample_waybill_no"]
        bag["es_context"] = info.get("es_context", "")
        bag["operation_time"] = info.get("operation_time", "")


def unsigned_cno_bag_serials(bag_rows: List[Dict[str, Any]]) -> List[str]:
    """未签入的 CNO.H 袋牌号列表（不含退件 R 开头）。"""
    return [
        str(b.get("serial_number") or "").strip()
        for b in bag_rows or []
        if is_cno_plan_unload_point(b.get("plan_unload_point"))
        and not is_return_bag(b.get("serial_number"))
        and int(b.get("cno_signed") or 0) == 0
        and str(b.get("serial_number") or "").strip()
    ]


def apply_trip_unload_display(
    trip: Dict[str, Any],
    *,
    first_signin_dt: Optional[datetime] = None,
    now: Optional[datetime] = None,
) -> None:
    """卸车用时：自实际抵达目的地站起算，至首件签入运单止；尚无签入则计至当前并标记 live。"""
    boxes = int(trip.get("transit_boxes_total") or 0)
    if boxes <= 0:
        trip.update(_empty_signin_summary())
        trip["transit_boxes_total"] = 0
        return

    arr_dt = _parse_la_dt(trip.get("actual_arrival_time"))
    if not arr_dt:
        return

    now = now or datetime.now(LA_TZ)
    if first_signin_dt is None:
        first_signin_dt = _parse_la_dt(trip.get("sign_in_time"))

    signed_count = int(trip.get("cno_signed_bag_count") or 0)
    trip["unload_start_time"] = _fmt_dt(arr_dt)

    has_first_signin = (
        signed_count > 0
        and first_signin_dt is not None
        and first_signin_dt >= arr_dt
    )
    if has_first_signin:
        trip["sign_in_time"] = _fmt_dt(first_signin_dt)
        end_dt = first_signin_dt
        trip["unload_live"] = False
    else:
        if not str(trip.get("sign_in_time") or "").strip():
            trip["sign_in_time"] = ""
        end_dt = now
        trip["unload_live"] = True

    span_secs = int((end_dt - arr_dt).total_seconds())
    span_secs = max(0, span_secs)
    trip["unload_duration_seconds"] = span_secs
    trip["unload_duration"] = _fmt_duration(timedelta(seconds=span_secs))
    trip["unload_start_seconds"] = span_secs
    trip["unload_timely"] = span_secs <= UNLOAD_WARN_SECONDS
    trip["unload_overtime"] = span_secs > UNLOAD_WARN_SECONDS


def _signin_summary_from_signin_map(
    signin_map: Dict[str, Dict[str, Any]],
    box_total: int,
    actual_arrival_time: str,
) -> Dict[str, Any]:
    summary = _empty_signin_summary()
    if box_total <= 0:
        return summary

    bag_times: List[Tuple[str, datetime]] = []
    signed_count = 0
    for pkg, info in signin_map.items():
        if int(info.get("cno_signed") or 0) != 1:
            continue
        signed_count += 1
        dt = _parse_operation_time(info.get("operation_time", ""))
        if dt:
            bag_times.append((info.get("operation_time", ""), dt))

    summary["cno_signed_bag_count"] = signed_count
    summary["bags_incomplete"] = signed_count < box_total

    first_dt: Optional[datetime] = None
    if bag_times:
        _, first_dt = min(bag_times, key=lambda x: x[1])

    stub = {
        "transit_boxes_total": box_total,
        "actual_arrival_time": actual_arrival_time,
        "sign_in_time": _fmt_dt(first_dt) if first_dt else "",
    }
    apply_trip_unload_display(stub, first_signin_dt=first_dt)
    for key in (
        "sign_in_time",
        "unload_start_time",
        "unload_start_seconds",
        "unload_timely",
        "unload_duration",
        "unload_duration_seconds",
        "unload_overtime",
        "unload_live",
    ):
        summary[key] = stub.get(key)
    return summary


def _first_page_waybill_nos_for_package(package_no: str) -> List[str]:
    """袋内运单第一页（用于判断是否存在 CNO.H 签入，不要求最新节点为签入）。"""
    package_no = (package_no or "").strip()
    if not package_no:
        return []
    recs, _ = _fetch_center_pack_page(package_no, 1, PACK_WAYBILL_PAGE_SIZE)
    nos: List[str] = []
    seen: set = set()
    for rec in recs:
        if not isinstance(rec, dict):
            continue
        wb = str(rec.get("waybillNo") or "").strip()
        if not wb or wb in seen:
            continue
        seen.add(wb)
        nos.append(wb)
    return nos


def _first_page_waybills_for_packages(
    package_nos: List[str],
    max_workers: int = 8,
) -> Dict[str, List[str]]:
    unique = []
    seen: set = set()
    for raw in package_nos:
        pkg = str(raw or "").strip()
        if not pkg or pkg in seen:
            continue
        seen.add(pkg)
        unique.append(pkg)
    if not unique:
        return {}

    out: Dict[str, List[str]] = {}

    def _one(pkg: str) -> Tuple[str, List[str]]:
        return pkg, _first_page_waybill_nos_for_package(pkg)

    workers = min(max_workers, len(unique))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_one, pkg): pkg for pkg in unique}
        for fut in as_completed(futs):
            pkg, wbs = fut.result()
            if wbs:
                out[pkg] = wbs
    return out


def _signin_summary_from_cno_bags(
    cno_bags: List[Dict[str, Any]],
    actual_arrival_time: str,
) -> Dict[str, Any]:
    """CNO.H 计划袋牌：取每袋首票运单轨迹，抵达后最早 CNO.H 签入计为本次到车签入。"""
    signin_map = _compute_cno_bag_signin_map(cno_bags, actual_arrival_time)
    return _signin_summary_from_signin_map(signin_map, len(cno_bags), actual_arrival_time)


def trip_signin_summary_from_stored_bags(
    bag_rows: List[Dict[str, Any]],
    actual_arrival_time: str,
) -> Dict[str, Any]:
    """根据已入库袋牌的 cno_signed / operation_time 汇总车次签入指标。"""
    cno_bags = filter_signin_eligible_bags(bag_rows)
    signin_map: Dict[str, Dict[str, Any]] = {}
    for bag in cno_bags:
        if int(bag.get("cno_signed") or 0) != 1:
            continue
        pkg = str(bag.get("serial_number") or "").strip()
        if not pkg:
            continue
        signin_map[pkg] = {
            "cno_signed": 1,
            "sample_waybill_no": bag.get("sample_waybill_no") or "",
            "es_context": bag.get("es_context") or "",
            "operation_time": bag.get("operation_time") or "",
        }
    return _signin_summary_from_signin_map(signin_map, len(cno_bags), actual_arrival_time)


def _list_bag_serials_for_task(
    task_no: str,
    task_arrival_id: int,
    *,
    cno_plan_only: bool = False,
) -> List[str]:
    rows: List[str] = []
    seen: set = set()
    for page in range(1, MAX_POPOVER_PAGES + 1):
        recs, _ = _fetch_load_bag_page(task_no, task_arrival_id, page, BAG_PAGE_SIZE)
        if not recs:
            break
        for rec in recs:
            if not isinstance(rec, dict):
                continue
            if cno_plan_only:
                plan_pt = str(rec.get("planUnLoadMeridianStopPoint") or "").strip()
                if not is_cno_plan_unload_point(plan_pt):
                    continue
            sn = str(rec.get("serialNumber") or "").strip()
            if not sn or sn in seen:
                continue
            seen.add(sn)
            rows.append(sn)
        if len(recs) < BAG_PAGE_SIZE:
            break
    return rows


def _empty_signin_summary() -> Dict[str, Any]:
    return {
        "cno_signed_bag_count": 0,
        "sign_in_time": "",
        "unload_start_time": "",
        "unload_start_seconds": None,
        "unload_timely": False,
        "unload_duration": "",
        "unload_duration_seconds": 0,
        "unload_overtime": False,
        "unload_live": False,
        "bags_incomplete": False,
    }


def _enrich_arrival_rows_with_signin(rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    workers = min(4, len(rows))

    def _job(row: Dict[str, Any]) -> Dict[str, Any]:
        try:
            arrival_id = int(row.get("task_arrival_id"))
        except (TypeError, ValueError):
            return _empty_signin_summary()
        api_boxes = int(row.get("transit_boxes_total") or 0)
        if api_boxes <= 0:
            row["transit_boxes_total"] = 0
            return _empty_signin_summary()
        bag_data = fetch_load_bag_details(row.get("task_no") or "", arrival_id, enrich_tracks=False)
        apply_trip_bag_metrics(row, bag_data.get("rows") or [])
        return {
            k: row.get(k)
            for k in _empty_signin_summary().keys()
        }

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [(row, ex.submit(_job, row)) for row in rows]
        for row, fut in futs:
            row.update(fut.result())


def fetch_waybill_tracks_batch(order_nos: List[str]) -> Dict[str, Dict[str, str]]:
    """批量查询运单轨迹最新节点（按 operationTime 取最新 es_context、operationTime）。"""
    unique = []
    seen: set = set()
    for raw in order_nos or []:
        no = str(raw or "").strip()
        if not no or no in seen:
            continue
        seen.add(no)
        unique.append(no)
    if not unique:
        return {}

    out: Dict[str, Dict[str, str]] = {}
    token = get_gofo_token()
    for i in range(0, len(unique), TRACK_BATCH_SIZE):
        chunk = unique[i : i + TRACK_BATCH_SIZE]
        items = _fetch_waybill_track_batch(chunk, token=token)
        for item in items:
            wb = _extract_waybill_no_from_track_item(item)
            if wb:
                out[wb] = _latest_track_from_item(item)
    return out


def fetch_waybill_track_detail(waybill_no: str) -> Dict[str, Any]:
    """单票运单轨迹明细（最新一条 + 完整 list）。"""
    waybill_no = (waybill_no or "").strip()
    if not waybill_no:
        raise ValueError("缺少 waybill_no")

    items = _fetch_waybill_track_batch([waybill_no])
    item = items[0] if items else {}
    lst = item.get("list") or []
    tracks: List[Dict[str, str]] = []
    if isinstance(lst, list):
        for ev in lst:
            if isinstance(ev, dict):
                tracks.append(_normalize_track_event(ev))
    latest = _newest_track_from_item(item) if item else {"es_context": "", "operation_time": ""}
    now_la = datetime.now(LA_TZ)
    return {
        "waybill_no": waybill_no,
        "es_context": latest["es_context"],
        "operation_time": latest["operation_time"],
        "tracks": tracks,
        "fetched_at": now_la.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _attach_tracks_to_rows(rows: List[Dict[str, Any]], *, key_field: str) -> None:
    order_nos = [str(r.get(key_field) or "").strip() for r in rows]
    tracks = fetch_waybill_tracks_batch(order_nos)
    for row in rows:
        wb = str(row.get(key_field) or "").strip()
        ev = tracks.get(wb) or {}
        row["es_context"] = ev.get("es_context", "")
        raw_time = ev.get("operation_time", "")
        row["operation_time"] = _fmt_dt(raw_time) or raw_time


def _list_waybill_nos_for_package(package_no: str) -> List[str]:
    package_no = (package_no or "").strip()
    if not package_no:
        return []
    nos: List[str] = []
    seen: set = set()
    for page in range(1, MAX_POPOVER_PAGES + 1):
        recs, _ = _fetch_center_pack_page(package_no, page, PACK_WAYBILL_PAGE_SIZE)
        if not recs:
            break
        for rec in recs:
            if not isinstance(rec, dict):
                continue
            wb = str(rec.get("waybillNo") or "").strip()
            if not wb or wb in seen:
                continue
            seen.add(wb)
            nos.append(wb)
        if len(recs) < PACK_WAYBILL_PAGE_SIZE:
            break
    return nos


def _waybill_nos_for_packages(package_nos: List[str], max_workers: int = 8) -> Dict[str, List[str]]:
    unique = []
    seen: set = set()
    for raw in package_nos:
        pkg = str(raw or "").strip()
        if not pkg or pkg in seen:
            continue
        seen.add(pkg)
        unique.append(pkg)
    if not unique:
        return {}

    out: Dict[str, List[str]] = {}

    def _one(pkg: str) -> Tuple[str, List[str]]:
        return pkg, _list_waybill_nos_for_package(pkg)

    workers = min(max_workers, len(unique))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_one, pkg): pkg for pkg in unique}
        for fut in as_completed(futs):
            pkg, wbs = fut.result()
            if wbs:
                out[pkg] = wbs
    return out


def _earliest_bag_signin(
    waybills: List[str],
    signins: Dict[str, Dict[str, str]],
) -> Optional[Tuple[Dict[str, str], datetime]]:
    best: Optional[Tuple[Dict[str, str], datetime]] = None
    for wb in waybills:
        ev = signins.get(wb)
        if not ev:
            continue
        dt = _parse_operation_time(ev.get("operation_time", ""))
        if not dt:
            continue
        if best is None or dt < best[1]:
            best = (ev, dt)
    return best


def _first_waybill_for_package(package_no: str) -> str:
    recs, _ = _fetch_center_pack_page(package_no, 1, 1)
    if recs and isinstance(recs[0], dict):
        return str(recs[0].get("waybillNo") or "").strip()
    return ""


def _first_waybills_for_packages(package_nos: List[str], max_workers: int = 8) -> Dict[str, str]:
    unique = []
    seen: set = set()
    for raw in package_nos:
        pkg = str(raw or "").strip()
        if not pkg or pkg in seen:
            continue
        seen.add(pkg)
        unique.append(pkg)
    if not unique:
        return {}

    out: Dict[str, str] = {}

    def _one(pkg: str) -> Tuple[str, str]:
        return pkg, _first_waybill_for_package(pkg)

    workers = min(max_workers, len(unique))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_one, pkg): pkg for pkg in unique}
        for fut in as_completed(futs):
            pkg, wb = fut.result()
            if wb:
                out[pkg] = wb
    return out


def _enrich_bags_with_tracks(
    rows: List[Dict[str, Any]],
    *,
    after_dt: Optional[datetime] = None,
) -> None:
    if not rows:
        return
    pkg_to_wbs = _first_page_waybills_for_packages([r.get("serial_number") for r in rows])
    all_wbs = [wb for wbs in pkg_to_wbs.values() for wb in wbs]
    signins = (
        fetch_waybill_signin_events_batch(all_wbs, after_dt=after_dt, trip_arrival_dt=after_dt)
        if all_wbs
        else {}
    )
    for row in rows:
        pkg = str(row.get("serial_number") or "").strip()
        wbs = pkg_to_wbs.get(pkg) or []
        hit = _earliest_signin_among_waybills(wbs, signins)
        if hit:
            wb, ev, dt = hit
            row["sample_waybill_no"] = wb
            row["es_context"] = ev.get("es_context", "")
            row["operation_time"] = _fmt_dt(dt)
        else:
            row["sample_waybill_no"] = wbs[0] if wbs else ""
            row["es_context"] = ""
            row["operation_time"] = ""
