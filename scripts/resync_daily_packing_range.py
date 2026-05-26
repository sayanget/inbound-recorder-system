"""按日强制重拉看板 + operlog 逐条，可选推送到 Neon。用法:
  python scripts/resync_daily_packing_range.py 2026-05-19 2026-05-25
  python scripts/resync_daily_packing_range.py 2026-05-19 2026-05-25 --push-neon
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

WINDOWS = ("calendar", "business", "seventeen")


def _parse_ymd(s: str) -> date:
    return datetime.strptime(s.strip()[:10], "%Y-%m-%d").date()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("start", help="起始运营日 YYYY-MM-DD")
    ap.add_argument("end", help="结束运营日 YYYY-MM-DD（含）")
    ap.add_argument("--push-neon", action="store_true", help="完成后推送到 Neon")
    ap.add_argument(
        "--windows",
        default=",".join(WINDOWS),
        help="stats_window，逗号分隔，默认三种",
    )
    ap.add_argument("--board-only", action="store_true", help="仅看板")
    ap.add_argument("--operlog-only", action="store_true", help="仅 operlog")
    ap.add_argument(
        "--skip",
        default="",
        help="跳过的运营日，逗号分隔，如 2026-05-18",
    )
    args = ap.parse_args()

    start = _parse_ymd(args.start)
    end = _parse_ymd(args.end)
    if start > end:
        print("start > end", file=sys.stderr)
        return 2
    windows = [w.strip() for w in args.windows.split(",") if w.strip()]
    for w in windows:
        if w not in WINDOWS:
            print(f"invalid window: {w}", file=sys.stderr)
            return 2

    skip_dates = {
        _parse_ymd(x) for x in args.skip.split(",") if x.strip()
    }

    import sync_daily_packing_board as board
    import sync_daily_packing_operlog as operlog

    d = start
    while d <= end:
        if d in skip_dates:
            print(f"[skip] {d.strftime('%Y-%m-%d')}")
            d += timedelta(days=1)
            continue
        ds = d.strftime("%Y-%m-%d")
        for wm in windows:
            if not args.operlog_only:
                br = board.sync_daily_packing_board_anchor(d, wm, force=True)
                print(
                    f"[board] {ds} {wm} ok={br.get('success')} "
                    f"man={br.get('manual_count')} dev={br.get('device_count')}"
                )
            if not args.board_only:
                orr = operlog.sync_daily_packing_operlog_anchor(d, wm, force=True)
                print(
                    f"[operlog] {ds} {wm} ok={orr.get('success')} "
                    f"rows={orr.get('raw_rows')} man={orr.get('manual_raw')} dev={orr.get('device_raw')}"
                )
        d += timedelta(days=1)

    if args.push_neon:
        import subprocess

        push = ROOT / "scripts" / "push_daily_packing_cache_to_neon.py"
        subprocess.run(
            [
                sys.executable,
                str(push),
                start.strftime("%Y-%m-%d"),
                end.strftime("%Y-%m-%d"),
            ],
            check=True,
            cwd=str(ROOT),
        )

    print(f"Done {start} .. {end}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
