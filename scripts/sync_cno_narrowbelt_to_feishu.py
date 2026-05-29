# Copyright (c) 2026 Fan Yang. All rights reserved.
"""一次性将 statistics「CNO 直线窄带分拣产能（按线）」写入飞书 eEZ3Ly。

用法:
  python scripts/sync_cno_narrowbelt_to_feishu.py          # 默认整批重写当前运营日（与统计页一致）
  python scripts/sync_cno_narrowbelt_to_feishu.py --incremental  # 仅追加有量且未写入的整点
  python scripts/sync_cno_narrowbelt_to_feishu.py --reset    # 同默认（显式重写运营日）
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    import single_app

    incremental = "--incremental" in sys.argv
    single_app.init_db()
    info = single_app.feishu_sync_cno_narrowbelt_sheet_once(
        replace_operating_day=not incremental,
    )
    print("OK", info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
