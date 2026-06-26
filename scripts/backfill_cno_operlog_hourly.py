#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
补拉 CNO 窄带分拣 + 劳务公司 Sorter 分时 operatelog（scan 217）。

写入表：
  - cno_narrowbelt_hourly
  - cno_labor_sorter_account_hourly / cno_labor_sorter_hourly（经 persist_hour_slot_from_rows）
  - 小组矩阵可由页面读库时从 account 表聚合

用法：
  python scripts/backfill_cno_operlog_hourly.py --date 2026-06-17
  python scripts/backfill_cno_operlog_hourly.py --start 2026-06-15 --end 2026-06-17
  python scripts/backfill_cno_operlog_hourly.py --start 2026-06-17 --end 2026-06-17 --hour-end 22
  python scripts/backfill_cno_operlog_hourly.py --yesterday   # 昨日满 24h
  python scripts/backfill_cno_operlog_hourly.py --yesterday --today  # 昨日 + 今日至今
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytz  # noqa: E402

from sync_cno_narrowbelt_hourly import (  # noqa: E402
    LA_TZ,
    sync_la_calendar_day_hours,
    sync_one_la_window,
)


def _date_range(start_str: str, end_str: str) -> list[str]:
    s = datetime.strptime(start_str[:10], "%Y-%m-%d").date()
    e = datetime.strptime(end_str[:10], "%Y-%m-%d").date()
    if s > e:
        s, e = e, s
    out = []
    d = s
    while d <= e:
        out.append(d.strftime("%Y-%m-%d"))
        d += timedelta(days=1)
    return out


def sync_day_partial(
    record_date_str: str,
    *,
    hour_start: int = 0,
    hour_end: int = 23,
) -> dict:
    """仅拉取某日 [hour_start, hour_end] 整点（LA），用于 token 中断后补 23 点前等片段。"""
    record_date_str = (record_date_str or "").strip()[:10]
    d = datetime.strptime(record_date_str, "%Y-%m-%d").date()
    day_start = LA_TZ.localize(datetime(d.year, d.month, d.day, 0, 0, 0))
    now = datetime.now(LA_TZ)
    hour_start = max(0, min(23, int(hour_start)))
    hour_end = max(hour_start, min(23, int(hour_end)))

    detail = []
    errors = []
    for h in range(hour_start, hour_end + 1):
        slot = day_start + timedelta(hours=h)
        if slot.strftime("%Y-%m-%d") != record_date_str:
            continue
        natural_end = slot + timedelta(hours=1) - timedelta(seconds=1)
        if d == now.date():
            if slot > now:
                break
            slot_end = min(natural_end, now)
        else:
            slot_end = natural_end
        try:
            detail.append(sync_one_la_window(slot, slot_end))
        except Exception as ex:
            errors.append({"slot": slot.isoformat(), "error": str(ex)})

    return {
        "success": len(errors) == 0,
        "date": record_date_str,
        "hour_range": f"{hour_start:02d}-{hour_end:02d}",
        "hours_attempted": len(detail),
        "errors": errors,
        "detail": detail,
    }


def main() -> int:
    la_today = datetime.now(LA_TZ).date()
    yesterday = (la_today - timedelta(days=1)).strftime("%Y-%m-%d")
    today = la_today.strftime("%Y-%m-%d")

    ap = argparse.ArgumentParser(description="补拉 CNO 窄带 + 劳务 Sorter 分时 operatelog")
    ap.add_argument("--date", help="单日 YYYY-MM-DD（拉满该 LA 日或今日至今）")
    ap.add_argument("--start", help="范围起 YYYY-MM-DD")
    ap.add_argument("--end", help="范围止 YYYY-MM-DD")
    ap.add_argument("--yesterday", action="store_true", help=f"补昨日 LA 日（{yesterday}）")
    ap.add_argument("--today", action="store_true", help=f"补今日 LA 日至今（{today}）")
    ap.add_argument("--hour-start", type=int, default=None, help="仅补该日从此整点起（0-23）")
    ap.add_argument("--hour-end", type=int, default=None, help="仅补该日到此整点止（0-23）")
    args = ap.parse_args()

    dates: list[str] = []
    if args.date:
        dates = [args.date[:10]]
    elif args.start or args.end:
        dates = _date_range(args.start or args.end, args.end or args.start)
    else:
        if args.yesterday:
            dates.append(yesterday)
        if args.today:
            dates.append(today)
        if not dates:
            dates = [yesterday]

    partial = args.hour_start is not None or args.hour_end is not None
    h0 = 0 if args.hour_start is None else args.hour_start
    h1 = 23 if args.hour_end is None else args.hour_end

    exit_code = 0
    for d in dates:
        print(f"\n=== CNO operlog backfill {d} ===")
        if partial and len(dates) == 1:
            result = sync_day_partial(d, hour_start=h0, hour_end=h1)
        else:
            result = sync_la_calendar_day_hours(d)
        ok = result.get("success")
        hrs = result.get("hours_attempted")
        errs = result.get("errors") or []
        print(f"  success={ok} hours={hrs} errors={len(errs)}")
        if errs:
            exit_code = 1
            for e in errs[:8]:
                print(f"    {e}")
        else:
            last = (result.get("detail") or [])[-1:] or []
            if last:
                r0 = last[0]
                print(
                    f"  last_slot={r0.get('time_slot')} "
                    f"rows={r0.get('raw_rows')} labor={r0.get('labor_sorter', {})}"
                )

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
