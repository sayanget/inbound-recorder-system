#!/usr/bin/env python3
"""
从 Gofo 按日历日重抓 chart_v2 + 逐小时 overview，回填 sorting_records（人工/设备/件数），
并在开启 GOFO_USE_POPOVER_HOURLY 时写入 popover 口径与 gofo_collect_destin_hourly（CNO01 等）。

用法:
  python backfill_gofo.py --today              # 仅洛杉矶「今天」
  python backfill_gofo.py 2026-04-03 2026-04-05
  python backfill_gofo.py 2026-04-03          # 单日

依赖: 与运行 single_app 相同（GOFO_TOKEN / gofo_token.txt / system_config gofo_admin_token）。
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    parser = argparse.ArgumentParser(description='Gofo sorting_records 区间回填（含 popover/CNO01）')
    parser.add_argument(
        '--today',
        action='store_true',
        help='只补洛杉矶时区今天的数据（等价于起止日均为今天）',
    )
    parser.add_argument('start_date', nargs='?', help='起始日 YYYY-MM-DD（与 --today 互斥）')
    parser.add_argument('end_date', nargs='?', help='结束日 YYYY-MM-DD，默认同起始日')
    args = parser.parse_args()
    os.chdir(ROOT)
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from single_app import perform_gofo_backfill_range, perform_gofo_backfill_today

    if args.today:
        print('回填: 洛杉矶今天')
        result = perform_gofo_backfill_today()
        print(result)
        return
    if not args.start_date:
        parser.error('请指定 --today 或起始日期 YYYY-MM-DD')
    end = args.end_date or args.start_date
    print(f'回填区间: {args.start_date} ~ {end}')
    result = perform_gofo_backfill_range(args.start_date, end)
    print(result)


if __name__ == '__main__':
    main()
