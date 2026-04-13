#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
读取 GoFO「中心看板」https://dms.gofoexpress.com/gofo-report/report/reportCenter/centerViewingBoard
中「查看明细-集包数」弹窗内，按目的组织查询后的 **集包袋数 / 集包运单数**。

**弹窗列表接口**（与页面「集包袋数 / 集包运单数」列一致）：

  POST .../dbu_report/common/magic/center/board/collectionPackage/popover

请求体示例（与浏览器一致）：

  ``{"destinIds":[],"dataType":217,"type":"collectTotalCnt","centerIds":[596],"pageNum":1,"pageSize":10,
  "startTime":"...","endTime":"..."}``

响应 `records[]` 中：**packageNoTotal** = 集包袋数，**waybillNoTotal** = 集包运单数，**destinName** = 目的组织代码。

筛选某目的站时可传 **destinIds: [目的站点 id]**，或传空数组由脚本分页按 **destinName** 匹配 **--site**。

请求头：`Channel-Id`、`User-Time-Zone`、`timeZone`、`Date-Time-Format`、`lang` 等（与前端一致）。
可用 `--popover-json` 覆盖/补充字段。

**列表/汇总备用接口**（分页明细行，含 targetSiteName、waybillCnt 等）：

  POST .../dbu_report/common/magic/center/board/status/details_v2
  - **status=4**：集包相关明细（status=2 为签入明细，见 sync_center_checkin.py）。

弹窗筛选「今日 17:00～当前」时，details_v2 常同时带 **timeArr** 与外层 **startTime/endTime**；是否与页面表格完全一致以实际 Payload 为准。

Token：GOFO_TOKEN / gofo_token.txt / system_config gofo_admin_token（gofo_config.get_gofo_token）。

示例：
  python scripts/read_gofo_center_collect_waybill.py --site CNO01 --since-hour 17
  python scripts/read_gofo_center_collect_waybill.py --endpoint details_v2 --site CNO01
  python scripts/read_gofo_center_collect_waybill.py --popover-json extra.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import requests  # noqa: E402

from gofo_config import get_gofo_token  # noqa: E402

URL_DETAILS_V2 = "https://dms.gofoexpress.com/prod-api/dbu_report/common/magic/center/board/status/details_v2"
URL_COLLECTION_PACKAGE_POPOVER = (
    "https://dms.gofoexpress.com/prod-api/dbu_report/common/magic/center/board/collectionPackage/popover"
)

DEFAULT_CENTER_ID = 596
DEFAULT_STATUS_COLLECT = 4
DEFAULT_POPOVER_TYPE = "collectTotalCnt"
DEFAULT_POPOVER_DATA_TYPE = 217
DEFAULT_POPOVER_PAGE_SIZE = 100
# 与 single_app.perform_gofo_hourly_sync 中看板日期一致（洛杉矶）
DEFAULT_BOARD_TZ = os.environ.get("GOFO_BOARD_TIMEZONE", "America/Los_Angeles")


def _board_headers(token: str, *, popover: bool = False) -> dict:
    h = {
        "Admin-Token": token,
        "Authorization": f"Bearer {token}",
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "lang": "zh",
    }
    if popover:
        h["Channel-Id"] = "us"
        h["User-Time-Zone"] = "America/Los_Angeles"
        h["timeZone"] = "GMT-0700"
        h["Date-Time-Format"] = "MM/dd/yyyy HH:mm:ss"
        h["Origin"] = "https://dms.gofoexpress.com"
    else:
        h["channel-id"] = "us"
        h["user-time-zone"] = "America/Los_Angeles"
    return h


def fetch_collect_details(
    *,
    target_site: str,
    center_id: int,
    start_time: str,
    end_time: str,
    status: int = DEFAULT_STATUS_COLLECT,
    data_type: int = 200,
    time_arr: list[str] | None = None,
) -> dict:
    token = get_gofo_token()
    headers = _board_headers(token, popover=False)
    page_num = 1
    page_size = 500
    all_rows: list = []

    while True:
        payload = {
            "status": status,
            "centerIds": [center_id],
            "timeArr": time_arr if time_arr is not None else [],
            "endDateTime": "",
            "nextNodeList": [],
            "targetCenterId": center_id,
            "startTime": start_time,
            "endTime": end_time,
            "pageNum": page_num,
            "pageSize": page_size,
            "dataType": data_type,
            "groupType": 2,
        }
        res = requests.post(URL_DETAILS_V2, headers=headers, json=payload, timeout=60)
        res.raise_for_status()
        body = res.json()
        if body.get("code") == 401:
            raise RuntimeError("Gofo API 登录失效，请更新 Token。")
        if body.get("code") != 200:
            raise RuntimeError(body.get("msg") or str(body))

        data = body.get("data") or {}
        records = data.get("records") or []
        total = int(data.get("total") or 0)
        all_rows.extend(records)
        if len(all_rows) >= total or not records:
            break
        page_num += 1

    site_upper = target_site.strip().upper()
    for row in all_rows:
        name = (row.get("targetSiteName") or "").strip().upper()
        if name == site_upper:
            return row
    return {}


def resolve_destin_id(
    *,
    target_site: str,
    center_id: int,
    start_time: str,
    end_time: str,
    time_arr: list[str] | None,
    status: int = DEFAULT_STATUS_COLLECT,
) -> int | None:
    """从 details_v2 行中解析 targetSiteId。"""
    row = fetch_collect_details(
        target_site=target_site,
        center_id=center_id,
        start_time=start_time,
        end_time=end_time,
        status=status,
        time_arr=time_arr,
    )
    if not row:
        return None
    sid = row.get("targetSiteId")
    return int(sid) if sid is not None else None


def fetch_collection_package_popover(payload: dict) -> dict:
    """POST collectionPackage/popover，返回接口 JSON。"""
    token = get_gofo_token()
    headers = _board_headers(token, popover=True)
    res = requests.post(URL_COLLECTION_PACKAGE_POPOVER, headers=headers, json=payload, timeout=60)
    res.raise_for_status()
    body = res.json()
    if body.get("code") == 401:
        raise RuntimeError("Gofo API 登录失效，请更新 Token。")
    return body


def popover_find_site_row(
    merged_no_page: dict,
    *,
    target_site: str,
    page_size: int,
) -> dict:
    """
    collectionPackage/popover：在 records 中按 destinName 匹配 target_site。
    merged_no_page 不含 pageNum/pageSize；若 destinIds 为单元素，通常只一页。
    """
    site_u = target_site.strip().upper()
    destin_ids = merged_no_page.get("destinIds")
    single_id = isinstance(destin_ids, list) and len(destin_ids) == 1

    page_num = 1
    while True:
        payload = {**merged_no_page, "pageNum": page_num, "pageSize": page_size}
        body = fetch_collection_package_popover(payload)
        if body.get("code") != 200:
            raise RuntimeError(body.get("message") or str(body))
        data = body.get("data") or {}
        records = data.get("records") or []
        total = int(data.get("total") or 0)
        for rec in records:
            name = (rec.get("destinName") or "").strip().upper()
            if name == site_u:
                return rec
        if single_id:
            return {}
        if page_num * page_size >= total or not records:
            break
        page_num += 1
    return {}


def main() -> None:
    p = argparse.ArgumentParser(
        description="读取中心看板「集包数」弹窗：details_v2 和/或 collectionPackage/popover"
    )
    p.add_argument("--site", default="CNO01", help="目的组织/站点代码，如 CNO01")
    p.add_argument(
        "--status",
        type=int,
        default=DEFAULT_STATUS_COLLECT,
        help="details_v2 的 status（默认 4=集包数弹窗；2=签入明细）",
    )
    p.add_argument("--center-id", type=int, default=DEFAULT_CENTER_ID, help="中心 ID（默认 596=CNO.H）")
    p.add_argument(
        "--date",
        help="报表日历日 YYYY-MM-DD。无 --since-hour 时表示该日 00:00～当日结束；与 --since-hour 联用表示该日 hour 点起算分段",
    )
    p.add_argument(
        "--tz",
        default=DEFAULT_BOARD_TZ,
        help=f"看板时间时区（默认 {DEFAULT_BOARD_TZ}，可用环境变量 GOFO_BOARD_TIMEZONE 覆盖）",
    )
    p.add_argument(
        "--since-hour",
        type=int,
        metavar="H",
        help="从当日 H 点整到现在（与 --date 合用指定哪一天）；会设置 timeArr=[起点, 现在]，外层 startTime/endTime 见 --outer-range",
    )
    p.add_argument(
        "--outer-range",
        choices=("day", "segment"),
        default="day",
        help="配合 --since-hour：outer startTime 用「终点日」00:00:00（day）或「起点」所在日 00:00:00（segment）；默认 day，与此前探测一致",
    )
    p.add_argument(
        "--start-time",
        help="直接指定外层 startTime（YYYY-MM-DD HH:MM:SS），覆盖 --since-hour 的外层起点",
    )
    p.add_argument(
        "--end-time",
        help="直接指定外层 endTime（YYYY-MM-DD HH:MM:SS），默认当前时刻（所给时区）",
    )
    p.add_argument(
        "--time-arr",
        metavar="JSON",
        help='JSON 数组，如 \'[\"2026-04-09 17:00:00\",\"2026-04-09 18:00:00\"]\'，覆盖自动 timeArr',
    )
    p.add_argument(
        "--endpoint",
        choices=("details_v2", "popover", "both"),
        default="popover",
        help="数据源：popover=集包弹窗 collectTotalCnt（默认）；details_v2=status 明细；both=两者",
    )
    p.add_argument(
        "--popover-type",
        default=DEFAULT_POPOVER_TYPE,
        help=f"popover 请求 type（默认 {DEFAULT_POPOVER_TYPE}）",
    )
    p.add_argument(
        "--popover-data-type",
        type=int,
        default=DEFAULT_POPOVER_DATA_TYPE,
        help=f"popover 请求 dataType（默认 {DEFAULT_POPOVER_DATA_TYPE}）",
    )
    p.add_argument(
        "--popover-page-size",
        type=int,
        default=DEFAULT_POPOVER_PAGE_SIZE,
        metavar="N",
        help="popover 分页 pageSize",
    )
    p.add_argument(
        "--popover-json",
        metavar="FILE",
        help="JSON 文件，与自动生成的 popover 请求体合并（后者覆盖前者同名字段）",
    )
    p.add_argument(
        "--destin-id",
        type=int,
        metavar="ID",
        help="目的站点 ID（不填则根据 --site 从 details_v2 解析 targetSiteId）",
    )
    p.add_argument("--json", action="store_true", help="打印整行 JSON")
    args = p.parse_args()

    tz = ZoneInfo(args.tz)
    now = datetime.now(tz)
    today_str = now.strftime("%Y-%m-%d")

    if args.end_time:
        end_time = args.end_time
    elif args.date and args.since_hour is None:
        end_time = (
            now.strftime("%Y-%m-%d %H:%M:%S")
            if args.date == today_str
            else f"{args.date} 23:59:59"
        )
    else:
        end_time = now.strftime("%Y-%m-%d %H:%M:%S")

    time_arr: list[str] | None = None
    if args.time_arr:
        time_arr = json.loads(args.time_arr)
        if not isinstance(time_arr, list) or len(time_arr) != 2:
            raise SystemExit("--time-arr 必须是含两个时间字符串的 JSON 数组")
    elif args.since_hour is not None:
        day_str = args.date or now.strftime("%Y-%m-%d")
        day0 = datetime.strptime(day_str, "%Y-%m-%d").date()
        day_start = datetime(day0.year, day0.month, day0.day, 0, 0, 0, tzinfo=tz)
        seg0 = day_start.replace(hour=args.since_hour, minute=0, second=0, microsecond=0)
        if now < seg0:
            seg_start_dt = seg0 - timedelta(days=1)
        else:
            seg_start_dt = seg0
        seg_start = seg_start_dt.strftime("%Y-%m-%d %H:%M:%S")
        seg_end = end_time
        time_arr = [seg_start, seg_end]

    if args.start_time:
        start_time = args.start_time
    elif args.date and args.since_hour is None:
        start_time = f"{args.date} 00:00:00"
    else:
        end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz)
        if args.outer_range == "day":
            outer_day = end_dt.strftime("%Y-%m-%d")
        else:
            if time_arr:
                seg0 = datetime.strptime(time_arr[0], "%Y-%m-%d %H:%M:%S").replace(tzinfo=tz)
                outer_day = seg0.strftime("%Y-%m-%d")
            else:
                outer_day = end_dt.strftime("%Y-%m-%d")
        start_time = f"{outer_day} 00:00:00"

    query_meta = {
        "startTime": start_time,
        "endTime": end_time,
        "timeArr": time_arr or [],
        "tz": args.tz,
    }

    popover_start = time_arr[0] if time_arr else start_time
    popover_end = time_arr[1] if time_arr else end_time
    query_meta["popoverStart"] = popover_start
    query_meta["popoverEnd"] = popover_end

    popover_bundle: dict | None = None
    pop_row: dict | None = None
    if args.endpoint in ("popover", "both"):
        destin_id = args.destin_id
        if destin_id is None:
            destin_id = resolve_destin_id(
                target_site=args.site,
                center_id=args.center_id,
                start_time=start_time,
                end_time=end_time,
                time_arr=time_arr,
                status=args.status,
            )

        popover_merged: dict = {
            "destinIds": [destin_id] if destin_id is not None else [],
            "dataType": args.popover_data_type,
            "type": args.popover_type,
            "centerIds": [args.center_id],
            "startTime": popover_start,
            "endTime": popover_end,
        }
        if args.popover_json:
            with open(args.popover_json, encoding="utf-8") as f:
                extra = json.load(f)
            if not isinstance(extra, dict):
                raise SystemExit("--popover-json 根必须是 JSON 对象")
            popover_merged = {**popover_merged, **extra}

        try:
            pop_row = popover_find_site_row(
                popover_merged,
                target_site=args.site,
                page_size=args.popover_page_size,
            )
        except Exception as e:
            print(f"popover 请求失败: {e}")
            sys.exit(1)

        popover_bundle = {
            "popover_request_template": popover_merged,
            "popover_matched_row": pop_row,
        }
        if not args.json:
            print("--- collectionPackage/popover (collectTotalCnt) ---")
            print(f"请求(无分页): {json.dumps(popover_merged, ensure_ascii=False)}")
            if pop_row:
                print(f"目的组织: {pop_row.get('destinName')}")
                print(f"集包袋数 (packageNoTotal): {pop_row.get('packageNoTotal')}")
                print(f"集包运单数 (waybillNoTotal): {pop_row.get('waybillNoTotal')}")
            else:
                print(f"未在 popover 结果中匹配目的站点 {args.site!r}（可改时间范围或传 --destin-id）。")
        if args.endpoint == "popover":
            if args.json:
                print(
                    json.dumps(
                        {**popover_bundle, "_query": query_meta},
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            if not pop_row:
                sys.exit(1)
            return

    row = fetch_collect_details(
        target_site=args.site,
        center_id=args.center_id,
        start_time=start_time,
        end_time=end_time,
        status=args.status,
        time_arr=time_arr,
    )
    if not row:
        print(f"未找到目的站点 {args.site!r} 的记录（请放宽时间或核对 center-id / Network 请求体）。")
        sys.exit(1)

    waybill = row.get("waybillCnt")
    bag = row.get("packageCnt") if (row.get("packageCnt") or 0) > 0 else row.get("checkInPackageCnt")
    if args.json:
        out = dict(row)
        out["_query"] = query_meta
        if popover_bundle:
            out["popover_request_template"] = popover_bundle["popover_request_template"]
            out["popover_matched_row"] = popover_bundle["popover_matched_row"]
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print("--- status/details_v2 ---")
        print(f"目的站点: {row.get('targetSiteName')}")
        print(f"集包袋数 (packageCnt / checkInPackageCnt): {bag}")
        print(f"集包运单数 (waybillCnt): {waybill}")
        print(
            f"(请求外层 startTime={start_time!r}, endTime={end_time!r}, "
            f"timeArr={time_arr!r})"
        )


if __name__ == "__main__":
    main()
