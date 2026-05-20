"""
每日集包（人工/设备）看板口径：与 Gofo overview 的 collectTotalCntArtificial / Device 一致。

按 stats_window 锚点日的运营窗口调用 magic/center/board/overview，缓存到 daily_packing_board_daily。
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

OVERVIEW_URL = "https://dms.gofoexpress.com/prod-api/dbu_report/common/magic/center/board/overview"


def parse_gofo_cnt(val) -> int:
    """与 perform_gofo_hourly_sync 一致：取「托盘/件数」中斜杠后件数。"""
    if val is None:
        return 0
    if isinstance(val, (int, float)):
        return int(val)
    if not isinstance(val, str) or not val.strip():
        return 0
    if "/" in val:
        try:
            return int(val.split("/")[-1].replace(",", "").strip())
        except ValueError:
            return 0
    try:
        return int(val.replace(",", "").strip())
    except ValueError:
        return 0


def _period_time_strings(anchor: date, window_mode: str) -> Tuple[str, str]:
    from single_app import _stats_period_bounds

    start, end = _stats_period_bounds(anchor, window_mode)
    end_incl = end - timedelta(seconds=1)
    return start.strftime("%Y-%m-%d %H:%M:%S"), end_incl.strftime("%Y-%m-%d %H:%M:%S")


def fetch_gofo_overview_split(
    start_time: str,
    end_time: str,
    *,
    center_ids: Optional[list] = None,
    max_retries: int = 3,
) -> Tuple[int, int, int]:
    """返回 (total, manual_artificial, device)。"""
    from gofo_config import get_gofo_token

    token = get_gofo_token()
    headers = {
        "Admin-Token": token,
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0",
        "channel-id": "us",
        "lang": "zh",
    }
    if center_ids is None:
        center_ids = [596]
    payload = {
        "centerIds": center_ids,
        "startTime": start_time,
        "endTime": end_time,
        "groupType": 2,
    }
    last_err = ""
    for attempt in range(max_retries):
        try:
            res = requests.post(OVERVIEW_URL, headers=headers, json=payload, timeout=25)
            if res.status_code != 200:
                last_err = f"HTTP {res.status_code}"
                time.sleep(1 + attempt)
                continue
            data = res.json()
            if data.get("code") == 401:
                raise RuntimeError("Gofo API 登录失效 (Token Expired)")
            if data.get("code") != 200:
                last_err = str(data.get("msg") or data)
                time.sleep(1 + attempt)
                continue
            body = data.get("data") or {}
            total = parse_gofo_cnt(body.get("collectTotalCnt"))
            manual = parse_gofo_cnt(body.get("collectTotalCntArtificial"))
            device = parse_gofo_cnt(body.get("collectTotalCntDevice"))
            if total <= 0 and (manual > 0 or device > 0):
                total = manual + device
            return total, manual, device
        except RuntimeError:
            raise
        except Exception as e:
            last_err = str(e)
            time.sleep(1 + attempt)
    raise RuntimeError(f"overview 请求失败 {start_time}..{end_time}: {last_err}")


def read_daily_packing_board_anchor(anchor: date, window_mode: str) -> Optional[Dict[str, int]]:
    from single_app import convert_query_placeholders, get_db

    anchor_str = anchor.strftime("%Y-%m-%d")
    wm = window_mode if window_mode in ("calendar", "business", "seventeen") else "calendar"
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            convert_query_placeholders(
                """
                SELECT manual_count, device_count, total_pieces
                FROM daily_packing_board_daily
                WHERE anchor_date = ? AND stats_window = ?
                """
            ),
            (anchor_str, wm),
        )
        r = cur.fetchone()
        if not r:
            return None
        return {
            "manual_count": int(r[0] or 0),
            "device_count": int(r[1] or 0),
            "total_pieces": int(r[2] or 0),
        }
    finally:
        conn.close()


def sync_daily_packing_board_anchor(
    anchor: date,
    window_mode: str = "calendar",
    *,
    force: bool = False,
) -> Dict[str, Any]:
    anchor_str = anchor.strftime("%Y-%m-%d")
    wm = window_mode if window_mode in ("calendar", "business", "seventeen") else "calendar"
    if not force:
        cached = read_daily_packing_board_anchor(anchor, wm)
        if cached is not None:
            return {"success": True, "cached": True, "anchor_date": anchor_str, "stats_window": wm, **cached}
    try:
        begin, end = _period_time_strings(anchor, wm)
        total, manual, device = fetch_gofo_overview_split(begin, end)
        if manual + device <= 0 and total > 0:
            manual, device = total, 0
        synced_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _write_cache(anchor_str, wm, manual, device, total, synced_at)
        return {
            "success": True,
            "cached": False,
            "anchor_date": anchor_str,
            "stats_window": wm,
            "manual_count": manual,
            "device_count": device,
            "total_pieces": total if total > 0 else manual + device,
        }
    except Exception as e:
        logger.warning("daily_packing board sync %s %s: %s", anchor_str, wm, e)
        return {"success": False, "error": str(e), "anchor_date": anchor_str, "stats_window": wm}


def _write_cache(
    anchor_str: str,
    window_mode: str,
    manual: int,
    device: int,
    total: int,
    synced_at: str,
) -> None:
    from single_app import get_db

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO daily_packing_board_daily
                (anchor_date, stats_window, manual_count, device_count, total_pieces, synced_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(anchor_date, stats_window) DO UPDATE SET
                manual_count = excluded.manual_count,
                device_count = excluded.device_count,
                total_pieces = excluded.total_pieces,
                synced_at = excluded.synced_at
            """,
            (anchor_str, window_mode, manual, device, total, synced_at),
        )
        conn.commit()
    finally:
        conn.close()
