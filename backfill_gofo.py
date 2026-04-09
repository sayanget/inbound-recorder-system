#!/usr/bin/env python3
"""
从 Gofo 按日历日重抓 chart_v2 + 逐小时 overview，回填 sorting_records（人工/设备/件数）。
用于更正某段日期在统计图中显示不准的问题。

用法:
  python backfill_gofo.py 2026-04-03 2026-04-05
  python backfill_gofo.py 2026-04-03          # 单日

依赖: 与运行 single_app 相同（GOFO_TOKEN / gofo_token.txt / system_config gofo_admin_token）。
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    parser = argparse.ArgumentParser(description='Gofo sorting_records 区间回填')
    parser.add_argument('start_date', help='起始日 YYYY-MM-DD')
    parser.add_argument('end_date', nargs='?', help='结束日 YYYY-MM-DD，默认同起始日')
    args = parser.parse_args()
    end = args.end_date or args.start_date
    os.chdir(ROOT)
    if ROOT not in sys.path:
        sys.path.insert(0, ROOT)
    from single_app import perform_gofo_backfill_range

    print(f'回填区间: {args.start_date} ~ {end}')
    result = perform_gofo_backfill_range(args.start_date, end)
    print(result)


if __name__ == '__main__':
    main()
