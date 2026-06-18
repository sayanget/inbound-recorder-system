#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 GoFO DMS 同步「到车情况 · 当日已到」到本地库（车次 + 袋牌）。

- 车次/袋牌：仅插入库中不存在的新任务，已入库数据不修改、不删除。
- 袋内运单：不在此脚本拉取；页面点击袋牌号时首次写入本地库，之后只读库。

用法:
  python scripts/sync_gofo_vehicle_arrival.py
  python scripts/sync_gofo_vehicle_arrival.py --date 2026-06-16
  python scripts/sync_gofo_vehicle_arrival.py --force   # 整日删后重拉（慎用）
  python scripts/sync_gofo_vehicle_arrival.py --repair-metrics  # 重算当日签入指标
"""
from __future__ import annotations

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import gofo_vehicle_arrival as gva  # noqa: E402
import gofo_vehicle_arrival_store as store  # noqa: E402

SYNC_TRIP_WORKERS = int(os.environ.get("GOFO_ARRIVAL_SYNC_WORKERS", "4"))


def _sync_one_trip(i: int, total: int, trip: Dict[str, Any]) -> Tuple[Optional[int], List[Dict[str, Any]]]:
    task_no = trip.get("task_no") or ""
    arrival_id = trip.get("task_arrival_id")
    if not task_no or arrival_id is None:
        return None, []
    api_boxes = int(trip.get("transit_boxes_total") or 0)
    if api_boxes <= 0:
        trip["transit_boxes_total"] = 0
        trip.update(gva._empty_signin_summary())
        print(f"  [{i}/{total}] {task_no} API装车箱数=0，跳过袋牌")
        return int(arrival_id), []
    try:
        t_trip = datetime.now()
        bag_data = gva.fetch_load_bag_details(task_no, arrival_id, enrich_tracks=False)
        bag_rows = bag_data.get("rows") or []
        for bag in bag_rows:
            bag["task_no"] = task_no
        gva.apply_trip_bag_metrics(trip, bag_rows)
        cno_boxes = int(trip.get("transit_boxes_total") or 0)
        secs = (datetime.now() - t_trip).total_seconds()
        print(
            f"  [{i}/{total}] {task_no} 袋牌 {len(bag_rows)}，CNO.H {cno_boxes}，"
            f"票数 {trip.get('waybill_total', 0)}，"
            f"签入箱 {trip.get('cno_signed_bag_count', 0)}，{secs:.1f}s"
        )
        return int(arrival_id), bag_rows
    except Exception as exc:
        print(f"  [{i}/{total}] {task_no} 袋牌失败: {exc}", file=sys.stderr)
        return int(arrival_id), []


def repair_signin_metrics(record_date: str) -> Dict[str, Any]:
    """重算当日所有车次签入指标（不删袋牌/运单）。"""
    t0 = datetime.now()
    synced_at = datetime.now(gva.LA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    trips = store.read_trips(record_date)
    if not trips:
        print(f"[repair] {record_date} 无车次")
        return {"record_date": record_date, "trips_repaired": 0, "elapsed": 0.0}

    try:
        popover_rows, _ = gva.fetch_arrival_popover_rows()
        gva.patch_trips_waybill_from_popover_rows(trips, popover_rows)
        store.persist_trips_waybill_totals(record_date, trips, synced_at=synced_at)
    except Exception as exc:
        print(f"[repair] 刷新 loadWaybillTotal 失败: {exc}", file=sys.stderr)

    total = len(trips)
    repaired = 0
    print(f"[repair] {record_date} 重算 {total} 车次签入指标（并行 {SYNC_TRIP_WORKERS}）…")

    def _job(i: int, trip: Dict[str, Any]) -> Optional[int]:
        task_no = trip.get("task_no") or ""
        arrival_id = trip.get("task_arrival_id")
        if not task_no or arrival_id is None:
            return None
        try:
            bag_data = gva.fetch_load_bag_details(task_no, arrival_id, enrich_tracks=False)
            bag_rows = bag_data.get("rows") or []
            gva.apply_trip_bag_metrics(trip, bag_rows)
            store.update_trip_signin_metrics(record_date, trip, synced_at=synced_at)
            store.update_bags_signin(record_date, int(arrival_id), bag_rows, synced_at=synced_at)
            unsigned = gva.unsigned_cno_bag_serials(bag_rows)
            print(
                f"  [{i}/{total}] {task_no} 签入箱 {trip.get('cno_signed_bag_count', 0)} "
                f"@ {trip.get('sign_in_time') or '-'}"
                + (f" 未签入 {len(unsigned)}: {', '.join(unsigned[:5])}" + ("…" if len(unsigned) > 5 else "") if unsigned else "")
            )
            return int(arrival_id)
        except Exception as exc:
            print(f"  [{i}/{total}] {task_no} 失败: {exc}", file=sys.stderr)
            return None

    workers = min(SYNC_TRIP_WORKERS, total)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_job, i, trip) for i, trip in enumerate(trips, 1)]
        for fut in as_completed(futs):
            if fut.result() is not None:
                repaired += 1
    elapsed = (datetime.now() - t0).total_seconds()
    store.update_day_stats(record_date)
    print(f"[repair] 完成 {record_date}: 更新 {repaired}/{total} 车次，耗时 {elapsed:.1f}s")
    return {"record_date": record_date, "trips_repaired": repaired, "elapsed": elapsed}


def sync_day(record_date: str, *, force: bool = False) -> Dict[str, Any]:
    t0 = datetime.now()
    synced_at = datetime.now(gva.LA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    existing_ids = store.list_all_trip_arrival_ids()

    print(f"[sync] {record_date} 拉取到车明细…")
    details = gva.fetch_arrival_details()
    trips = details.get("rows") or []
    summary = {
        "arrived_today": len(trips),
        "destination": details.get("destination"),
        "date_type": details.get("date_type"),
        "center_id": details.get("center_id"),
    }

    if force:
        to_fetch = trips
        print(f"[sync] --force：整日重拉 {len(to_fetch)} 车次（保留已写入运单）…")
    else:
        to_fetch = [
            t for t in trips
            if int(t.get("task_arrival_id") or 0) not in existing_ids
        ]
        print(
            f"[sync] DMS {len(trips)} 车次，库中 {len(existing_ids)}，"
            f"待新增 {len(to_fetch)}（并行 {SYNC_TRIP_WORKERS}）…"
        )
        if not to_fetch:
            repair_stats = store.repair_trip_record_dates(record_date)
            for d in repair_stats.get("dates_updated") or []:
                store.update_day_trip_count(d)
            arrived_count = store.update_day_trip_count(record_date)
            print("[sync] 无新车次，已入库数据不更新（运单请点击袋牌写入）")
            elapsed = (datetime.now() - t0).total_seconds()
            return {
                "record_date": record_date,
                "trips": len(trips),
                "arrived_today": arrived_count,
                "trips_inserted": 0,
                "bags_inserted": 0,
                "trips_skipped": len(trips),
                "trips_relocated": repair_stats.get("trips_moved", 0),
                "synced_at": synced_at,
                "elapsed": elapsed,
                "skipped": True,
            }

    bags_by_task: Dict[int, List[Dict[str, Any]]] = {}
    total = len(to_fetch)
    workers = min(SYNC_TRIP_WORKERS, total) if total else 1
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {
            ex.submit(_sync_one_trip, i, total, trip): trip
            for i, trip in enumerate(to_fetch, 1)
        }
        for fut in as_completed(futs):
            arrival_id, bag_rows = fut.result()
            if arrival_id is not None:
                bags_by_task[arrival_id] = bag_rows

    if force:
        store.save_day_snapshot(
            record_date,
            summary=summary,
            trips=to_fetch,
            bags_by_task=bags_by_task,
            waybills_by_package={},
            synced_at=synced_at,
            sync_waybills=False,
        )
        merge_stats = {
            "trips_inserted": len(to_fetch),
            "bags_inserted": sum(len(v) for v in bags_by_task.values()),
            "trips_skipped": 0,
        }
    else:
        merge_stats = store.merge_new_arrivals(
            record_date,
            summary=summary,
            trips=to_fetch,
            bags_by_task=bags_by_task,
            synced_at=synced_at,
        )

    arrived_count = store.update_day_trip_count(record_date)
    repair_stats = store.repair_trip_record_dates(record_date)
    for d in repair_stats.get("dates_updated") or []:
        if d != record_date:
            store.update_day_trip_count(d)
    elapsed = (datetime.now() - t0).total_seconds()
    print(
        f"[sync] 完成 {record_date}: 库内车次={arrived_count} 新增车次={merge_stats['trips_inserted']} "
        f"新增袋牌={merge_stats['bags_inserted']} "
        f"跳过={merge_stats['trips_skipped']} "
        f"迁桶={repair_stats.get('trips_moved', 0)} @ {synced_at}，耗时 {elapsed:.1f}s"
    )
    return {
        "record_date": record_date,
        "trips": len(trips),
        "arrived_today": arrived_count,
        "synced_at": synced_at,
        "elapsed": elapsed,
        "trips_relocated": repair_stats.get("trips_moved", 0),
        **merge_stats,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="同步 GoFO 到车信息（增量：仅新车次；运单点击袋牌写入）")
    parser.add_argument("--date", help="统计日 YYYY-MM-DD（默认 LA 今日）")
    parser.add_argument(
        "--force",
        action="store_true",
        help="删除当日车次/袋牌后整日重拉（不删已有点击写入的运单）",
    )
    parser.add_argument(
        "--repair-metrics",
        action="store_true",
        help="重算当日已入库车次的签入时间/箱数（不删袋牌与运单）",
    )
    parser.add_argument(
        "--repair-waybills",
        action="store_true",
        help="从 raw_json loadWaybillTotal 回写车次装车总票数与 day 汇总（不拉袋牌）",
    )
    parser.add_argument(
        "--repair-dates",
        action="store_true",
        help="按 actual_arrival_time LA 日历日修正车次/袋牌 record_date 错桶",
    )
    args = parser.parse_args()
    record_date = (args.date or store.la_record_date()).strip()
    try:
        if args.repair_waybills:
            stats = store.repair_waybill_totals(record_date)
            print(
                f"[repair-waybills] {record_date}: "
                f"{stats['trips']} 车次，总票数 {stats['total_waybills']}"
            )
        elif args.repair_metrics:
            repair_signin_metrics(record_date)
        elif args.repair_dates:
            stats = store.repair_trip_record_dates(record_date if args.date else None)
            print(
                f"[repair-dates] 迁移 {stats['trips_moved']} 车次；"
                f"更新日: {', '.join(stats.get('dates_updated') or []) or '—'}"
            )
        else:
            sync_day(record_date, force=args.force)
        return 0
    except Exception as exc:
        print(f"[sync] 失败: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
