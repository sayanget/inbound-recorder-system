"""将本地 inbound.db 的每日集包缓存复制到 Neon（网站实际读的库）。"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _neon_url() -> str:
    for line in (ROOT / "neon_sync.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("DATABASE_URL="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("neon_sync.env 中未配置 DATABASE_URL")


def main() -> int:
    start = (sys.argv[1] if len(sys.argv) > 1 else "2026-05-12")[:10]
    end = (sys.argv[2] if len(sys.argv) > 2 else "2026-05-19")[:10]

    import psycopg2

    local = sqlite3.connect(ROOT / "inbound.db")
    pg = psycopg2.connect(_neon_url())
    pg.autocommit = False
    cur = pg.cursor()

    cur.execute(
        "ALTER TABLE daily_packing_operlog_daily "
        "ADD COLUMN IF NOT EXISTS classifier_ver INTEGER NOT NULL DEFAULT 0"
    )

    boards = local.execute(
        """
        SELECT anchor_date, stats_window, manual_count, device_count, total_pieces, synced_at
        FROM daily_packing_board_daily
        WHERE anchor_date >= ? AND anchor_date <= ?
        """,
        (start, end),
    ).fetchall()
    for row in boards:
        cur.execute(
            """
            INSERT INTO daily_packing_board_daily
                (anchor_date, stats_window, manual_count, device_count, total_pieces, synced_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (anchor_date, stats_window) DO UPDATE SET
                manual_count = EXCLUDED.manual_count,
                device_count = EXCLUDED.device_count,
                total_pieces = EXCLUDED.total_pieces,
                synced_at = EXCLUDED.synced_at
            """,
            row,
        )
    print(f"board rows upserted: {len(boards)}")

    operlogs = local.execute(
        """
        SELECT anchor_date, stats_window, manual_raw, device_raw, manual_dedup, device_dedup, synced_at,
               2
        FROM daily_packing_operlog_daily
        WHERE anchor_date >= ? AND anchor_date <= ?
        """,
        (start, end),
    ).fetchall()
    for row in operlogs:
        cur.execute(
            """
            INSERT INTO daily_packing_operlog_daily
                (anchor_date, stats_window, manual_raw, device_raw, manual_dedup, device_dedup, synced_at, classifier_ver)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (anchor_date, stats_window) DO UPDATE SET
                manual_raw = EXCLUDED.manual_raw,
                device_raw = EXCLUDED.device_raw,
                manual_dedup = EXCLUDED.manual_dedup,
                device_dedup = EXCLUDED.device_dedup,
                synced_at = EXCLUDED.synced_at,
                classifier_ver = EXCLUDED.classifier_ver
            """,
            row,
        )
    print(f"operlog rows upserted: {len(operlogs)}")

    pg.commit()
    local.close()
    pg.close()
    print(f"Done: pushed {start} .. {end} to Neon PostgreSQL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
