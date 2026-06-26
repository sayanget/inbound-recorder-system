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
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sync_cno_narrowbelt_hourly import fetch_operatelog_window, narrowbelt_line_from_operator

logger = logging.getLogger(__name__)

# 人工/设备判定规则变更时递增；读缓存时版本不一致则视为未同步，避免展示旧误判数据。
OPERLOG_CLASSIFIER_VERSION = 2

_operlog_sync_lock = threading.Lock()

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


def operlog_hourly_anchor_dates(window_mode: str) -> List[date]:
    """当前运营锚点日；17:00/05:00 窗口在换日前后多保留前一日（图表近 2 天）。"""
    from single_app import LA_TZ, _default_stats_request_date

    cur = _default_stats_request_date(window_mode)
    dates = [cur]
    prev = cur - timedelta(days=1)
    if window_mode in ("business", "seventeen") and prev not in dates:
        dates.insert(0, prev)
    return dates


def hourly_sync_windows_from_env() -> tuple[str, ...]:
    raw = (os.environ.get("DAILY_PACKING_OPERLOG_HOURLY_WINDOWS") or "seventeen").strip()
    out = []
    for part in raw.split(","):
        w = part.strip().lower()
        if w in ("calendar", "business", "seventeen") and w not in out:
            out.append(w)
    return tuple(out) if out else ("seventeen",)


def run_hourly_operlog_sync() -> Dict[str, Any]:
    """每小时：逐条 operlog 刷新当前运营日（持锁，避免与手动/上次任务重叠）。"""
    if os.environ.get("DISABLE_DAILY_PACKING_OPERLOG_HOURLY", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        return {"success": False, "skipped": True, "reason": "disabled"}

    if not _operlog_sync_lock.acquire(blocking=False):
        return {"success": False, "skipped": True, "reason": "sync_in_progress"}

    results: List[Dict[str, Any]] = []
    try:
        for wm in hourly_sync_windows_from_env():
            for anchor in operlog_hourly_anchor_dates(wm):
                res = sync_daily_packing_operlog_anchor(anchor, wm, force=True)
                results.append(res)
                logger.info(
                    "hourly operlog %s %s ok=%s man=%s dev=%s rows=%s",
                    anchor,
                    wm,
                    res.get("success"),
                    res.get("manual_raw"),
                    res.get("device_raw"),
                    res.get("raw_rows"),
                )
        _maybe_push_operlog_cache_to_neon()
        return {"success": True, "results": results}
    finally:
        _operlog_sync_lock.release()


def _maybe_push_operlog_cache_to_neon() -> None:
    """本机 SQLite 且配置了 neon_sync.env 时，把近 3 天 operlog 缓存推到 Neon。"""
    if os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL"):
        return
    root = Path(__file__).resolve().parent
    neon_env = root / "neon_sync.env"
    if not neon_env.is_file():
        return
    try:
        from single_app import LA_TZ

        end = datetime.now(LA_TZ).date()
        start = end - timedelta(days=2)
        import subprocess
        import sys

        push = root / "scripts" / "push_daily_packing_cache_to_neon.py"
        if not push.is_file():
            return
        subprocess.run(
            [
                sys.executable,
                str(push),
                start.strftime("%Y-%m-%d"),
                end.strftime("%Y-%m-%d"),
            ],
            cwd=str(root),
            timeout=120,
            check=False,
        )
    except Exception as e:
        logger.warning("neon push after hourly operlog: %s", e)


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
        _write_cache(
            anchor_str,
            wm,
            manual_raw,
            device_raw,
            manual_dedup,
            device_dedup,
            synced_at,
            OPERLOG_CLASSIFIER_VERSION,
        )
        return {
            "success": True,
            "cached": False,
            "anchor_date": anchor_str,
            "stats_window": wm,
            "period_begin": begin_str,
            "period_end": end_str,
            "manual_raw": manual_raw,
            "device_raw": device_raw,
            "manual_dedup": manual_dedup,
            "device_dedup": device_dedup,
            "raw_rows": len(rows),
            "classifier_ver": OPERLOG_CLASSIFIER_VERSION,
        }
    except Exception as e:
        logger.warning("daily_packing operlog sync %s %s: %s", anchor_str, wm, e)
        return {"success": False, "error": str(e), "anchor_date": anchor_str, "stats_window": wm}


def _ensure_operlog_cache_columns() -> None:
    """为 daily_packing_operlog_daily 增加 classifier_ver（SQLite / Postgres）。"""
    from single_app import USE_POSTGRES, get_db

    conn = get_db()
    cur = conn.cursor()
    try:
        if USE_POSTGRES:
            cur.execute(
                "ALTER TABLE daily_packing_operlog_daily "
                "ADD COLUMN IF NOT EXISTS classifier_ver INTEGER NOT NULL DEFAULT 0"
            )
        else:
            cur.execute("PRAGMA table_info(daily_packing_operlog_daily)")
            cols = {row[1] for row in cur.fetchall()}
            if "classifier_ver" not in cols:
                cur.execute(
                    "ALTER TABLE daily_packing_operlog_daily "
                    "ADD COLUMN classifier_ver INTEGER NOT NULL DEFAULT 0"
                )
        conn.commit()
    except Exception as e:
        logger.debug("operlog cache schema: %s", e)
    finally:
        conn.close()


def _read_cache(anchor_str: str, window_mode: str) -> Optional[Dict[str, int]]:
    from single_app import convert_query_placeholders, get_db

    _ensure_operlog_cache_columns()
    conn = get_db()
    cur = conn.cursor()
    try:
        has_ver = True
        try:
            cur.execute(
                convert_query_placeholders(
                    """
                    SELECT manual_raw, device_raw, manual_dedup, device_dedup, classifier_ver
                    FROM daily_packing_operlog_daily
                    WHERE anchor_date = ? AND stats_window = ?
                    """
                ),
                (anchor_str, window_mode),
            )
        except Exception:
            conn.rollback()
            has_ver = False
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
        ver = int(r[4] or 0) if has_ver and len(r) > 4 else OPERLOG_CLASSIFIER_VERSION
        # 仅当「设备异常高于人工」的旧坏缓存才因版本号作废；有正常件数且 ver=0 仍可读（避免图表全 0）
        if ver < OPERLOG_CLASSIFIER_VERSION and (
            device_raw > manual_raw * 2 and manual_raw < 50000 and device_raw > 100000
        ):
            logger.info(
                "invalidate operlog cache %s %s (classifier_ver=%s, inverted ratio)",
                anchor_str,
                window_mode,
                ver,
            )
            return None
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
    classifier_ver: int = OPERLOG_CLASSIFIER_VERSION,
) -> None:
    from single_app import get_db

    _ensure_operlog_cache_columns()
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO daily_packing_operlog_daily
                (anchor_date, stats_window, manual_raw, device_raw, manual_dedup, device_dedup, synced_at, classifier_ver)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(anchor_date, stats_window) DO UPDATE SET
                manual_raw = excluded.manual_raw,
                device_raw = excluded.device_raw,
                manual_dedup = excluded.manual_dedup,
                device_dedup = excluded.device_dedup,
                synced_at = excluded.synced_at,
                classifier_ver = excluded.classifier_ver
            """,
            (
                anchor_str,
                window_mode,
                manual_raw,
                device_raw,
                manual_dedup,
                device_dedup,
                synced_at,
                classifier_ver,
            ),
        )
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description="单日 operlog 集包同步（逐条，force，写入 daily_packing_operlog_daily）"
    )
    parser.add_argument("date", help="运营锚点日 YYYY-MM-DD")
    parser.add_argument(
        "-w",
        "--window",
        default=os.environ.get("STATS_WINDOW", "seventeen"),
        choices=("calendar", "business", "seventeen"),
        help="stats_window，默认 seventeen（当班次 17:00–次日17:00）或环境变量 STATS_WINDOW",
    )
    args = parser.parse_args()
    try:
        anchor = datetime.strptime(args.date.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        print("date 格式应为 YYYY-MM-DD", file=sys.stderr)
        sys.exit(2)
    out = sync_daily_packing_operlog_anchor(anchor, args.window, force=True)
    print(out)
    sys.exit(0 if out.get("success") else 1)
