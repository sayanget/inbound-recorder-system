"""一次性将 CNO 小组分时矩阵写入飞书电子表格「元数据」工作表。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    import single_app

    single_app.init_db()
    info = single_app.feishu_sync_cno_labor_group_hourly_sheet_once()
    print("OK", info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
