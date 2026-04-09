#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 GoFO DMS「运单管理查询」对应的后端列表接口分页拉取数据，写入表 gofo_waybill_manage_import。

字段：运单号、运单状态、计划始发中心、目的站点、快递员工作区名称（+ 源创建时间、筛选日期、批次、原始 JSON）。

配置接口 URL（必做）：
  浏览器打开
  https://dms.gofoexpress.com/gofo-waybill/order/waybillMgr/WaybillManageQuery
  登录后 F12 -> Network -> 筛选 Fetch/XHR -> 点击「查询」
  选中列表请求 -> Headers 里复制 Request URL，设为环境变量：
    set GOFO_WAYBILL_LIST_URL=https://dms.gofoexpress.com/prod-api/.../xxx

Token：与现有 GoFO 脚本一致（GOFO_TOKEN / gofo_token.txt / system_config gofo_admin_token），见 gofo_config.get_gofo_token。

若默认请求体与贵司接口不一致，使用 --body-style 或 --post-body-file（见 --help）。

用法示例：
  python scripts/import_gofo_waybill_manage.py --date 2026-04-01
  python scripts/import_gofo_waybill_manage.py --date 2026-04-01 --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

# 项目根目录
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import requests  # noqa: E402

from database import convert_sql, get_db_connection, get_placeholder, USE_POSTGRES  # noqa: E402
from gofo_config import get_gofo_token  # noqa: E402


DEFAULT_PAGE_SIZE = 500


def _headers(token: str) -> Dict[str, str]:
    return {
        "Admin-Token": token,
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://dms.gofoexpress.com",
        "Referer": "https://dms.gofoexpress.com/gofo-waybill/order/waybillMgr/WaybillManageQuery",
        "User-Agent": "Mozilla/5.0",
        "lang": "zh",
    }


def build_post_body(
    style: str,
    page_num: int,
    page_size: int,
    day_str: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """按日筛选创建时间（00:00:00 - 23:59:59）。"""
    begin = f"{day_str} 00:00:00"
    end = f"{day_str} 23:59:59"
    extra = dict(extra or {})
    if style == "ruoyi":
        base = {
            "pageNum": page_num,
            "pageSize": page_size,
            "params": {"beginTime": begin, "endTime": end},
        }
        ep = extra.pop("params", None)
        if isinstance(ep, dict):
            base["params"].update(ep)
        base.update(extra)
        return base
    if style == "flat":
        base = {
            "pageNum": page_num,
            "pageSize": page_size,
            "beginTime": begin,
            "endTime": end,
        }
        base.update(extra)
        return base
    if style == "create_range":
        base = {
            "pageNum": page_num,
            "pageSize": page_size,
            "createTimeStart": begin,
            "createTimeEnd": end,
        }
        base.update(extra)
        return base
    raise ValueError(f"unknown body style: {style}")


def load_post_body_file(path: str, page_num: int, page_size: int, day_str: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    begin = f"{day_str} 00:00:00"
    end = f"{day_str} 23:59:59"
    raw = (
        raw.replace("{{PAGE}}", str(page_num))
        .replace("{{SIZE}}", str(page_size))
        .replace("{{DATE}}", day_str)
        .replace("{{BEGIN}}", begin)
        .replace("{{END}}", end)
    )
    return json.loads(raw)


def dig_records(data: Any, records_path: Optional[str]) -> List[Dict[str, Any]]:
    if records_path:
        cur: Any = data
        for part in records_path.split("."):
            if cur is None:
                return []
            cur = cur.get(part) if isinstance(cur, dict) else None
        if isinstance(cur, list):
            return [x for x in cur if isinstance(x, dict)]
        return []
    if not isinstance(data, dict):
        return []
    d = data.get("data")
    if isinstance(d, dict):
        for key in ("records", "list", "rows"):
            v = d.get(key)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
    return []


def pick(row: Dict[str, Any], *keys: str) -> Optional[Any]:
    for k in keys:
        if k in row and row[k] is not None and row[k] != "":
            return row[k]
    return None


def extract_row(row: Dict[str, Any]) -> Tuple[str, Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
    waybill = pick(
        row,
        "waybillNo",
        "waybill_no",
        "trackingNo",
        "trackNo",
        "orderNo",
        "mailNo",
        "waybillCode",
    )
    if waybill is None:
        return "", None, None, None, None, None
    waybill_s = str(waybill).strip()
    status = pick(
        row,
        "waybillStatus",
        "waybillState",
        "statusName",
        "statusStr",
        "stateName",
        "waybillStatusName",
    )
    if status is not None:
        status = str(status)
    origin = pick(
        row,
        "planStartCenterName",
        "planBeginCenterName",
        "startCenterName",
        "originCenterName",
        "planOriginCenterName",
        "sendCenterName",
    )
    if origin is not None:
        origin = str(origin)
    dest = pick(
        row,
        "destStationName",
        "destinationStationName",
        "endSiteName",
        "destSiteName",
        "receiveSiteName",
        "toStationName",
    )
    if dest is not None:
        dest = str(dest)
    area = pick(
        row,
        "courierWorkAreaName",
        "workAreaName",
        "delivererWorkAreaName",
        "courierAreaName",
        "deliveryWorkAreaName",
    )
    if area is not None:
        area = str(area)
    raw_ct = pick(
        row,
        "createTime",
        "createdTime",
        "gmtCreate",
        "createDate",
    )
    ct = str(raw_ct) if raw_ct is not None else None
    return waybill_s, status, origin, dest, area, ct


_DATE_RE = re.compile(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})")


def parse_date_from_string(s: str) -> Optional[date]:
    if not s:
        return None
    m = _DATE_RE.search(s)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def ensure_table(cursor) -> None:
    sql = convert_sql(
        """CREATE TABLE IF NOT EXISTS gofo_waybill_manage_import (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            waybill_no TEXT NOT NULL,
            waybill_status TEXT,
            plan_origin_center TEXT,
            dest_station TEXT,
            courier_work_area_name TEXT,
            source_create_time TEXT,
            filter_create_date DATE NOT NULL,
            import_batch_id TEXT,
            raw_json TEXT,
            imported_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(waybill_no, filter_create_date)
        );"""
    )
    cursor.execute(sql)


def upsert_row_sqlite(cursor, ph: str, data: Tuple[Any, ...]) -> None:
    """SQLite: 先删后插（同 waybill_no + filter_create_date）。"""
    (
        waybill_no,
        waybill_status,
        plan_origin_center,
        dest_station,
        courier_work_area_name,
        source_create_time,
        filter_create_date,
        import_batch_id,
        raw_json,
    ) = data
    cursor.execute(
        f"DELETE FROM gofo_waybill_manage_import WHERE waybill_no = {ph} AND filter_create_date = {ph}",
        (waybill_no, filter_create_date),
    )
    cursor.execute(
        f"""
        INSERT INTO gofo_waybill_manage_import (
            waybill_no, waybill_status, plan_origin_center, dest_station, courier_work_area_name,
            source_create_time, filter_create_date, import_batch_id, raw_json
        ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
        """,
        data,
    )


def upsert_row_pg(cursor, ph: str, data: Tuple[Any, ...]) -> None:
    cursor.execute(
        f"""
        INSERT INTO gofo_waybill_manage_import (
            waybill_no, waybill_status, plan_origin_center, dest_station, courier_work_area_name,
            source_create_time, filter_create_date, import_batch_id, raw_json
        ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
        ON CONFLICT (waybill_no, filter_create_date) DO UPDATE SET
            waybill_status = EXCLUDED.waybill_status,
            plan_origin_center = EXCLUDED.plan_origin_center,
            dest_station = EXCLUDED.dest_station,
            courier_work_area_name = EXCLUDED.courier_work_area_name,
            source_create_time = EXCLUDED.source_create_time,
            import_batch_id = EXCLUDED.import_batch_id,
            raw_json = EXCLUDED.raw_json,
            imported_at = CURRENT_TIMESTAMP
        """,
        data,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Import GoFO DMS waybill query page data into DB.")
    ap.add_argument("--date", required=True, help="筛选创建日期 YYYY-MM-DD（如 2026-04-01）")
    ap.add_argument("--list-url", default=os.environ.get("GOFO_WAYBILL_LIST_URL", "").strip(), help="列表 POST 接口完整 URL（或设环境变量 GOFO_WAYBILL_LIST_URL）")
    ap.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    ap.add_argument("--body-style", choices=("ruoyi", "flat", "create_range"), default="ruoyi", help="请求体时间字段风格")
    ap.add_argument("--post-body-file", help="JSON 文件，支持占位符 {{PAGE}}{{SIZE}}{{DATE}}{{BEGIN}}{{END}}")
    ap.add_argument("--extra-json", help="合并到 POST JSON 的额外对象（JSON 字符串）")
    ap.add_argument("--records-path", help="响应中列表路径，如 data.records（默认自动识别）")
    ap.add_argument("--total-path", help="响应总条数字段，如 data.total（默认 data.total）")
    ap.add_argument("--no-row-date-filter", action="store_true", help="不在客户端按创建时间再筛一遍（默认会筛）")
    ap.add_argument("--dry-run", action="store_true", help="只打印首条请求与样例记录，不写库")
    args = ap.parse_args()

    list_url = args.list_url
    if not list_url:
        print(
            "错误：未设置列表接口 URL。请在浏览器 Network 中复制查询请求的 Request URL，\n"
            "  set GOFO_WAYBILL_LIST_URL=https://dms.gofoexpress.com/prod-api/...\n"
            "或使用参数: --list-url ...",
            file=sys.stderr,
        )
        return 2

    try:
        day = datetime.strptime(args.date, "%Y-%m-%d").date()
    except ValueError:
        print("错误：--date 须为 YYYY-MM-DD", file=sys.stderr)
        return 2
    day_str = day.isoformat()

    token = get_gofo_token()
    headers = _headers(token)
    extra: Dict[str, Any] = {}
    if args.extra_json:
        extra = json.loads(args.extra_json)

    batch_id = str(uuid.uuid4())[:12]
    total_inserted = 0
    page = 1
    total_expected: Optional[int] = None

    while True:
        if args.post_body_file:
            body = load_post_body_file(args.post_body_file, page, args.page_size, day_str)
        else:
            body = build_post_body(args.body_style, page, args.page_size, day_str, extra)

        if args.dry_run and page == 1:
            print("POST", list_url)
            print(json.dumps(body, ensure_ascii=False, indent=2))

        try:
            r = requests.post(list_url, headers=headers, json=body, timeout=120)
        except requests.RequestException as e:
            print(f"HTTP 请求失败: {e}", file=sys.stderr)
            return 1

        if r.status_code != 200:
            print(f"HTTP {r.status_code}: {r.text[:500]}", file=sys.stderr)
            return 1

        try:
            payload = r.json()
        except json.JSONDecodeError:
            print("响应不是 JSON", file=sys.stderr)
            return 1

        c = payload.get("code")
        if c is not None and str(c) not in ("200", "0"):
            print(f"业务错误: code={c} msg={payload.get('msg')}", file=sys.stderr)
            return 1

        data_root = payload.get("data")
        if args.total_path:
            cur: Any = payload
            for part in args.total_path.split("."):
                cur = cur.get(part) if isinstance(cur, dict) else None
            total_expected = int(cur) if cur is not None else None
        else:
            if isinstance(data_root, dict):
                t = data_root.get("total")
                if t is not None:
                    try:
                        total_expected = int(t)
                    except (TypeError, ValueError):
                        total_expected = None

        recs = dig_records(payload, args.records_path)
        if args.dry_run and page == 1:
            print("样例记录数:", len(recs))
            if recs:
                print("首条 keys:", list(recs[0].keys())[:40])

        ph = get_placeholder()
        if not args.dry_run:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                ensure_table(cursor)
                for rec in recs:
                    wb, st, o, d, a, ct = extract_row(rec)
                    if not wb:
                        continue
                    if not args.no_row_date_filter and ct:
                        pdt = parse_date_from_string(ct)
                        if pdt is not None and pdt != day:
                            continue
                    tup = (
                        wb,
                        st,
                        o,
                        d,
                        a,
                        ct,
                        day_str,
                        batch_id,
                        json.dumps(rec, ensure_ascii=False),
                    )
                    if USE_POSTGRES:
                        upsert_row_pg(cursor, ph, tup)
                    else:
                        upsert_row_sqlite(cursor, ph, tup)
                    total_inserted += 1

        if args.dry_run:
            return 0

        if not recs:
            break

        if total_expected is not None:
            if page * args.page_size >= total_expected or len(recs) < args.page_size:
                break
        else:
            if len(recs) < args.page_size:
                break
        page += 1

    print(f"完成：写入/更新 {total_inserted} 条（批次 {batch_id}，日期 {day_str}）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
