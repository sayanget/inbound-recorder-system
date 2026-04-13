"""
GoFO DMS collectionPackage/popover（type=collectTotalCnt）整段汇总。

用于按小时窗口汇总全中心各目的站「集包运单数」「集包袋数」，与页面弹窗口径一致。
"""
from __future__ import annotations

import os
from typing import Optional, Sequence, Tuple

import requests

from gofo_config import get_gofo_token

POPOVER_URL = (
    "https://dms.gofoexpress.com/prod-api/dbu_report/common/magic/center/board/collectionPackage/popover"
)

DEFAULT_DATA_TYPE = 217
DEFAULT_POPOVER_TYPE = "collectTotalCnt"
DEFAULT_PAGE_SIZE = 200


def _popover_headers(token: str) -> dict:
    return {
        "Admin-Token": token,
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Channel-Id": "us",
        "User-Time-Zone": "America/Los_Angeles",
        "timeZone": "GMT-0700",
        "Date-Time-Format": "MM/dd/yyyy HH:mm:ss",
        "lang": "zh",
        "Origin": "https://dms.gofoexpress.com",
    }


def sum_popover_collect_for_window(
    start_time: str,
    end_time: str,
    *,
    center_ids: Optional[Sequence[int]] = None,
    data_type: int = DEFAULT_DATA_TYPE,
    popover_type: str = DEFAULT_POPOVER_TYPE,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> Optional[Tuple[int, int]]:
    """
    对 [start_time, end_time] 调用 popover，分页累加所有 destin 的
    waybillNoTotal、packageNoTotal。

    返回 (waybill_sum, package_sum)；失败时返回 None。
    """
    raw = os.environ.get("GOFO_POPOVER_CENTER_IDS", "").strip()
    if center_ids is None:
        if raw:
            center_ids = [int(x.strip()) for x in raw.split(",") if x.strip()]
        else:
            center_ids = [596]

    token = get_gofo_token()
    headers = _popover_headers(token)

    base = {
        "destinIds": [],
        "dataType": data_type,
        "type": popover_type,
        "centerIds": list(center_ids),
        "startTime": start_time,
        "endTime": end_time,
    }

    waybill_sum = 0
    package_sum = 0
    page_num = 1

    while True:
        payload = {**base, "pageNum": page_num, "pageSize": page_size}
        try:
            res = requests.post(POPOVER_URL, headers=headers, json=payload, timeout=60)
            res.raise_for_status()
            body = res.json()
        except Exception:
            return None

        if body.get("code") == 401:
            return None
        if body.get("code") != 200:
            return None

        data = body.get("data") or {}
        records = data.get("records") or []
        total = int(data.get("total") or 0)

        for rec in records:
            w = rec.get("waybillNoTotal")
            p = rec.get("packageNoTotal")
            if w is not None:
                try:
                    waybill_sum += int(w)
                except (TypeError, ValueError):
                    pass
            if p is not None:
                try:
                    package_sum += int(p)
                except (TypeError, ValueError):
                    pass

        if page_num * page_size >= total or not records:
            break
        page_num += 1

    return (waybill_sum, package_sum)


def la_hour_window_strings(sorting_date: str, time_slot: str) -> Tuple[str, str]:
    """sorting_date='YYYY-MM-DD', time_slot='HH:00' -> LA 该小时起止字符串。"""
    h = time_slot.strip().split(":")[0].zfill(2)
    return (f"{sorting_date} {h}:00:00", f"{sorting_date} {h}:59:59")


def popover_destin_hour_totals(
    start_time: str,
    end_time: str,
    destin_id: int,
    *,
    center_ids: Optional[Sequence[int]] = None,
    data_type: int = DEFAULT_DATA_TYPE,
    popover_type: str = DEFAULT_POPOVER_TYPE,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> Optional[Tuple[int, int]]:
    """
    仅统计单个目的站（destinIds=[id]）的集包运单数 / 集包袋数。
    返回 (waybillNoTotal, packageNoTotal)；失败返回 None。
    """
    raw = os.environ.get("GOFO_POPOVER_CENTER_IDS", "").strip()
    if center_ids is None:
        if raw:
            center_ids = [int(x.strip()) for x in raw.split(",") if x.strip()]
        else:
            center_ids = [596]

    token = get_gofo_token()
    headers = _popover_headers(token)
    base = {
        "destinIds": [int(destin_id)],
        "dataType": data_type,
        "type": popover_type,
        "centerIds": list(center_ids),
        "startTime": start_time,
        "endTime": end_time,
    }
    waybill_sum = 0
    package_sum = 0
    page_num = 1
    while True:
        payload = {**base, "pageNum": page_num, "pageSize": page_size}
        try:
            res = requests.post(POPOVER_URL, headers=headers, json=payload, timeout=60)
            res.raise_for_status()
            body = res.json()
        except Exception:
            return None
        if body.get("code") == 401:
            return None
        if body.get("code") != 200:
            return None
        data = body.get("data") or {}
        records = data.get("records") or []
        total = int(data.get("total") or 0)
        for rec in records:
            w = rec.get("waybillNoTotal")
            p = rec.get("packageNoTotal")
            if w is not None:
                try:
                    waybill_sum += int(w)
                except (TypeError, ValueError):
                    pass
            if p is not None:
                try:
                    package_sum += int(p)
                except (TypeError, ValueError):
                    pass
        if page_num * page_size >= total or not records:
            break
        page_num += 1
    return (waybill_sum, package_sum)
