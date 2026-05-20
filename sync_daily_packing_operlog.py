"""
每日集包（人工/设备）operatelog 口径：按运营日窗口汇总 scan 217，区分人工/设备。

- 逐条：每条 operatelog 计 1
- 去重（operatelog）：按 (运单号, scanTypeStr, 操作员) 去重
- 看板（sorting_records）在 API 层单独读取，不在此模块写入

设备判定：操作员名称含 Sorter/分拣机/窄带/DWS 等（与计件脚本一致方向）。
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sync_cno_narrowbelt_hourly import fetch_operatelog_window, narrowbelt_line_from_operator

logger = logging.getLogger(__name__)

# 与 Gofo 看板 collectArtificial / collectDevice 对齐：
# - 「AAS Sorter」等人工分拣台算人工（Artificial），不能因含 Sorter 判为设备
# - CNO 直线窄带、DWS/自动分拣机等算设备
_DEVICE_NAME_MARKERS = (
    "DWS",
    "AUTOSORT",
    "AUTOMATIC",
    "直线窄带",
    "窄带分拣",
    "窄带分拣机",
    "自动分拣",
)


def operlog_row_is_device_packing(create_by_name: Any) -> bool:
    if narrowbelt_line_from_operator(create_by_name) is not None:
        return True
    n = str(create_by_name or "").strip()
    if not n:
        return False
    if "CNO直线" in n or "CNO直线窄带" in n.upper():
        return True
    u = n.upper()
    if "SORTER" in u and "CNO" not in u:
        return False
    for m in _DEVICE_NAME_MARKERS:
        mu = m.upper()
        if mu in u or m in n:
            return True
    return False


def counts_manual_device_both(
    rows: List[Dict[str, Any]],
) -> Tuple[int, int, int, int]:
    """(manual_raw, device_raw, manual_dedup, device_dedup)"""
    manual_raw = device_raw = manual_dedup = device_dedup = 0
    seen: set = set()
    for r in rows:
        op = r.get("createByName")
        is_dev = operlog_row_is_device_packing(op)
        if is_dev:
            device_raw += 1
        else:
            manual_raw += 1
        waybill = r.get("waybillNo") or ""
        st = r.get("scanTypeStr") or ""
        key = (waybill, st, op)
        if key in seen:
            continue
        seen.add(key)
        if is_dev:
            device_dedup += 1
        else:
            manual_dedup += 1
    return manual_raw, device_raw, manual_dedup, device_dedup


def _period_bounds_for_anchor(anchor: date, window_mode: str) -> Tuple[str, str]:
    from single_app import _stats_period_bounds

    start, end = _stats_period_bounds(anchor, window_mode)
    # operatelog 闭区间到秒；end 为次日 0 点则减 1 秒
    end_adj = end - timedelta(seconds=1)
    return start.strftime("%Y-%m-%d %H:%M:%S"), end_adj.strftime("%Y-%m-%d %H:%M:%S")


def read_daily_packing_operlog_anchor(
    anchor: date,
    window_mode: str = "calendar",
) -> Dict[str, Any]:
    """仅读 daily_packing_operlog_daily 缓存，不请求 operlog（避免统计页 HTTP 长时间阻塞）。"""
    anchor_str = anchor.strftime("%Y-%m-%d")
    wm = window_mode if window_mode in ("calendar", "business", "seventeen") else "calendar"
    cached = _read_cache(anchor_str, wm)
    if cached is not None:
        return {"success": True, "cached": True, "anchor_date": anchor_str, "stats_window": wm, **cached}
    return {"success": False, "cached": False, "anchor_date": anchor_str, "stats_window": wm}


def sync_daily_packing_operlog_anchor(
    anchor: date,
    window_mode: str = "calendar",
    *,
    force: bool = False,
) -> Dict[str, Any]:
    """拉取并 UPSERT daily_packing_operlog_daily；失败时返回 success=False。"""
    anchor_str = anchor.strftime("%Y-%m-%d")
    wm = window_mode if window_mode in ("calendar", "business", "seventeen") else "calendar"

    if not force:
        cached = _read_cache(anchor_str, wm)
        if cached is not None:
            return {"success": True, "cached": True, **cached}

    try:
        begin_str, end_str = _period_bounds_for_anchor(anchor, wm)
        rows = fetch_operatelog_window(begin_str, end_str)
        manual_raw, device_raw, manual_dedup, device_dedup = counts_manual_device_both(rows)
        synced_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _write_cache(anchor_str, wm, manual_raw, device_raw, manual_dedup, device_dedup, synced_at)
        return {
            "success": True,
            "cached": False,
            "anchor_date": anchor_str,
            "stats_window": wm,
            "manual_raw": manual_raw,
            "device_raw": device_raw,
            "manual_dedup": manual_dedup,
            "device_dedup": device_dedup,
            "raw_rows": len(rows),
        }
    except Exception as e:
        logger.warning("daily_packing operlog sync %s %s: %s", anchor_str, wm, e)
        return {"success": False, "error": str(e), "anchor_date": anchor_str, "stats_window": wm}


def _read_cache(anchor_str: str, window_mode: str) -> Optional[Dict[str, int]]:
    from single_app import convert_query_placeholders, get_db

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            convert_query_placeholders(
                """
                SELECT manual_raw, device_raw, manual_dedup, device_dedup
                FROM daily_packing_operlog_daily
                WHERE anchor_date = ? AND stats_window = ?
                """
            ),
            (anchor_str, window_mode),
        )
        r = cur.fetchone()
        if not r:
            return None
        manual_raw = int(r[0] or 0)
        device_raw = int(r[1] or 0)
        # 旧版误将含 Sorter 的人工台计为设备，缓存比例倒置时作废
        if device_raw > manual_raw * 2 and manual_raw < 50000 and device_raw > 100000:
            logger.info(
                "invalidate stale operlog cache %s %s (manual_raw=%s device_raw=%s)",
                anchor_str,
                window_mode,
                manual_raw,
                device_raw,
            )
            return None
        return {
            "manual_raw": manual_raw,
            "device_raw": device_raw,
            "manual_dedup": int(r[2] or 0),
            "device_dedup": int(r[3] or 0),
        }
    finally:
        conn.close()


def _write_cache(
    anchor_str: str,
    window_mode: str,
    manual_raw: int,
    device_raw: int,
    manual_dedup: int,
    device_dedup: int,
    synced_at: str,
) -> None:
    from single_app import get_db

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO daily_packing_operlog_daily
                (anchor_date, stats_window, manual_raw, device_raw, manual_dedup, device_dedup, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(anchor_date, stats_window) DO UPDATE SET
                manual_raw = excluded.manual_raw,
                device_raw = excluded.device_raw,
                manual_dedup = excluded.manual_dedup,
                device_dedup = excluded.device_dedup,
                synced_at = excluded.synced_at
            """,
            (anchor_str, window_mode, manual_raw, device_raw, manual_dedup, device_dedup, synced_at),
        )
        conn.commit()
    finally:
        conn.close()
