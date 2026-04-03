#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""将 outbound_records 中 route_type = 'regular' 的行改为 branch（与 API normalize 一致）。可安全重复执行。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection


def main():
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE outbound_records SET route_type = 'branch' "
            "WHERE LOWER(TRIM(COALESCE(route_type, ''))) = 'regular'"
        )
        n = cur.rowcount
        print(f"Updated outbound_records rows from route_type=regular to branch: {n}")


if __name__ == "__main__":
    main()
