# Copyright (c) 2026 Fan Yang. All rights reserved.
"""到货信息本地库：表结构、读写（页面/API 只读库，GoFO 由 sync 脚本写入）。"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import pytz

from database import convert_placeholders, convert_sql, get_db_connection

LA_TZ = pytz.timezone("America/Los_Angeles")

TABLE_DAY = "gofo_vehicle_arrival_day"
TABLE_TRIP = "gofo_vehicle_arrival_trip"
TABLE_BAG = "gofo_vehicle_arrival_bag"
TABLE_WAYBILL = "gofo_vehicle_arrival_package_waybill"


def la_record_date() -> str:
    return datetime.now(LA_TZ).strftime("%Y-%m-%d")


def list_record_dates(limit: int = 90) -> List[Dict[str, Any]]:
    """本地库已有到车数据的日期（降序）。"""
    ensure_tables()
    with get_db_connection() as conn:
        cur = conn.cursor()
        q, p = convert_placeholders(
            f"""
            SELECT d.record_date,
                   COALESCE(d.arrived_today, 0) AS arrived_today,
                   COALESCE(d.synced_at, '') AS synced_at,
                   COALESCE(t.trip_count, 0) AS trip_count
            FROM {TABLE_DAY} d
            LEFT JOIN (
                SELECT record_date, COUNT(*) AS trip_count
                FROM {TABLE_TRIP}
                GROUP BY record_date
            ) t ON t.record_date = d.record_date
            ORDER BY d.record_date DESC
            LIMIT ?
            """,
            (int(limit),),
        )
        cur.execute(q, p)
        rows = [_dict_row(r) for r in cur.fetchall()]
    if rows:
        return rows
    # day 表无行时，仍可能仅有 trip（历史异常）；从 trip 汇总
    with get_db_connection() as conn:
        cur = conn.cursor()
        q, p = convert_placeholders(
            f"""
            SELECT record_date, COUNT(*) AS trip_count
            FROM {TABLE_TRIP}
            GROUP BY record_date
            ORDER BY record_date DESC
            LIMIT ?
            """,
            (int(limit),),
        )
        cur.execute(q, p)
        return [
            {
                "record_date": _dict_row(r).get("record_date"),
                "arrived_today": _dict_row(r).get("trip_count") or 0,
                "trip_count": _dict_row(r).get("trip_count") or 0,
                "synced_at": "",
            }
            for r in cur.fetchall()
        ]


def ensure_tables() -> None:
    ddl = [
        convert_sql(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_DAY} (
            record_date    TEXT PRIMARY KEY,
            arrived_today  INTEGER DEFAULT 0,
            destination    TEXT,
            date_type      TEXT,
            center_id      INTEGER,
            synced_at      TEXT
        )"""),
        convert_sql(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_TRIP} (
            record_date              TEXT NOT NULL,
            task_arrival_id          INTEGER NOT NULL,
            task_no                  TEXT NOT NULL,
            place_of_origin          TEXT,
            destination              TEXT,
            actual_departure_time    TEXT,
            actual_arrival_time      TEXT,
            transit_boxes_total      INTEGER DEFAULT 0,
            waybill_total            INTEGER DEFAULT 0,
            line_name                TEXT,
            license_plate_no         TEXT,
            task_status_str          TEXT,
            cno_signed_bag_count     INTEGER DEFAULT 0,
            sign_in_time             TEXT,
            unload_duration          TEXT,
            unload_duration_seconds  INTEGER DEFAULT 0,
            unload_overtime          INTEGER DEFAULT 0,
            unload_live              INTEGER DEFAULT 0,
            bags_incomplete          INTEGER DEFAULT 0,
            unload_start_time        TEXT,
            unload_start_seconds     INTEGER,
            unload_timely            INTEGER DEFAULT 0,
            raw_json                 TEXT,
            synced_at                TEXT,
            PRIMARY KEY (record_date, task_arrival_id)
        )"""),
        convert_sql(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_BAG} (
            record_date              TEXT NOT NULL,
            task_arrival_id          INTEGER NOT NULL,
            task_no                  TEXT NOT NULL,
            serial_number            TEXT NOT NULL,
            load_scan_time           TEXT,
            scan_type                TEXT,
            load_point               TEXT,
            plan_unload_point        TEXT,
            unload_point             TEXT,
            unload_scan_time         TEXT,
            sample_waybill_no        TEXT,
            es_context               TEXT,
            operation_time           TEXT,
            cno_signed               INTEGER,
            synced_at                TEXT,
            PRIMARY KEY (record_date, task_arrival_id, serial_number)
        )"""),
        convert_sql(f"""
        CREATE TABLE IF NOT EXISTS {TABLE_WAYBILL} (
            record_date              TEXT NOT NULL,
            package_no               TEXT NOT NULL,
            waybill_no               TEXT NOT NULL,
            to_code                  TEXT,
            to_state                 TEXT,
            to_city                  TEXT,
            es_context               TEXT,
            operation_time           TEXT,
            synced_at                TEXT,
            PRIMARY KEY (record_date, package_no, waybill_no)
        )"""),
    ]
    indexes = [
        f"CREATE INDEX IF NOT EXISTS idx_gva_trip_date ON {TABLE_TRIP}(record_date)",
        f"CREATE INDEX IF NOT EXISTS idx_gva_bag_task ON {TABLE_BAG}(record_date, task_arrival_id)",
        f"CREATE INDEX IF NOT EXISTS idx_gva_wb_pkg ON {TABLE_WAYBILL}(record_date, package_no)",
    ]
    with get_db_connection() as conn:
        cur = conn.cursor()
        for sql in ddl:
            cur.execute(sql)
        for sql in indexes:
            cur.execute(sql)
        _ensure_trip_columns(cur)
        _ensure_bag_columns(cur)
        _ensure_day_columns(cur)


def _ensure_day_columns(cur) -> None:
    for col, typedef in (
        ("cno_signed_boxes_total", "INTEGER DEFAULT 0"),
        ("total_waybills", "INTEGER DEFAULT 0"),
    ):
        try:
            cur.execute(f"SELECT {col} FROM {TABLE_DAY} LIMIT 1")
        except Exception:
            try:
                cur.execute(f"ALTER TABLE {TABLE_DAY} ADD COLUMN {col} {typedef}")
            except Exception:
                pass


def _ensure_bag_columns(cur) -> None:
    for col, typedef in (
        ("cno_signed", "INTEGER"),
    ):
        try:
            cur.execute(f"SELECT {col} FROM {TABLE_BAG} LIMIT 1")
        except Exception:
            try:
                cur.execute(f"ALTER TABLE {TABLE_BAG} ADD COLUMN {col} {typedef}")
            except Exception:
                pass


def _ensure_trip_columns(cur) -> None:
    """已有库补列。"""
    for col, typedef in (
        ("unload_overtime", "INTEGER DEFAULT 0"),
        ("unload_duration_seconds", "INTEGER DEFAULT 0"),
        ("unload_live", "INTEGER DEFAULT 0"),
        ("bags_incomplete", "INTEGER DEFAULT 0"),
        ("unload_start_time", "TEXT"),
        ("unload_start_seconds", "INTEGER"),
        ("unload_timely", "INTEGER DEFAULT 0"),
    ):
        try:
            cur.execute(f"SELECT {col} FROM {TABLE_TRIP} LIMIT 1")
        except Exception:
            try:
                cur.execute(f"ALTER TABLE {TABLE_TRIP} ADD COLUMN {col} {typedef}")
            except Exception:
                pass


def _delete_day(cur, record_date: str, *, include_waybills: bool = True) -> None:
    tables = [
        (TABLE_BAG, "record_date"),
        (TABLE_TRIP, "record_date"),
        (TABLE_DAY, "record_date"),
    ]
    if include_waybills:
        tables.insert(0, (TABLE_WAYBILL, "record_date"))
    for tbl, col in tables:
        q, p = convert_placeholders(f"DELETE FROM {tbl} WHERE {col} = ?", (record_date,))
        cur.execute(q, p)


def _insert_waybill_rows(
    cur,
    record_date: str,
    package_no: str,
    rows: List[Dict[str, Any]],
    synced_at: str,
) -> None:
    wb_sql = f"""
        INSERT INTO {TABLE_WAYBILL} (
            record_date, package_no, waybill_no, to_code, to_state, to_city,
            es_context, operation_time, synced_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    for wb in rows:
        q, p = convert_placeholders(
            wb_sql,
            (
                record_date,
                package_no,
                wb.get("waybill_no"),
                wb.get("to_code"),
                wb.get("to_state"),
                wb.get("to_city"),
                wb.get("es_context"),
                wb.get("operation_time"),
                synced_at,
            ),
        )
        cur.execute(q, p)


def upsert_package_waybills(
    package_no: str,
    rows: List[Dict[str, Any]],
    *,
    record_date: Optional[str] = None,
    synced_at: Optional[str] = None,
) -> int:
    """写入/覆盖某袋牌当日运单明细。"""
    package_no = (package_no or "").strip()
    record_date = (record_date or la_record_date()).strip()
    if not package_no:
        return 0
    ensure_tables()
    synced_at = synced_at or datetime.now(LA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    with get_db_connection() as conn:
        cur = conn.cursor()
        q, p = convert_placeholders(
            f"DELETE FROM {TABLE_WAYBILL} WHERE record_date = ? AND package_no = ?",
            (record_date, package_no),
        )
        cur.execute(q, p)
        if rows:
            _insert_waybill_rows(cur, record_date, package_no, rows, synced_at)
    return len(rows)


def ensure_package_waybills(
    package_no: str,
    *,
    record_date: Optional[str] = None,
) -> Dict[str, Any]:
    """每次点击袋牌从 GoFO 拉取最新运单与轨迹，并回写袋牌签入状态。"""
    record_date = (record_date or la_record_date()).strip()
    import gofo_vehicle_arrival as gva

    package_no = package_no.strip()
    arrival_time = ""
    with get_db_connection() as conn:
        cur = conn.cursor()
        q, p = convert_placeholders(
            f"""SELECT t.actual_arrival_time
            FROM {TABLE_BAG} b
            INNER JOIN {TABLE_TRIP} t
              ON t.record_date = b.record_date AND t.task_arrival_id = b.task_arrival_id
            WHERE b.record_date = ? AND b.serial_number = ?
            LIMIT 1""",
            (record_date, package_no),
        )
        cur.execute(q, p)
        bag_ctx = _dict_row(cur.fetchone())
        arrival_time = (bag_ctx or {}).get("actual_arrival_time") or ""

    fetched = gva.fetch_package_waybill_details(
        package_no,
        actual_arrival_time=arrival_time or None,
    )
    rows = fetched.get("rows") or []
    upsert_package_waybills(package_no, rows, record_date=record_date)
    refresh_bag_signin_for_package(package_no, record_date=record_date)
    data = read_package_waybills(package_no, record_date=record_date)
    data["from_cache"] = False
    data["refreshed_at"] = fetched.get("fetched_at") or ""
    with get_db_connection() as conn:
        cur = conn.cursor()
        q, p = convert_placeholders(
            f"""SELECT t.task_arrival_id, t.transit_boxes_total, t.cno_signed_bag_count, t.bags_incomplete,
                b.cno_signed, b.es_context, b.operation_time
            FROM {TABLE_BAG} b
            INNER JOIN {TABLE_TRIP} t
              ON t.record_date = b.record_date AND t.task_arrival_id = b.task_arrival_id
            WHERE b.record_date = ? AND b.serial_number = ?
            LIMIT 1""",
            (record_date, package_no.strip()),
        )
        cur.execute(q, p)
        trip_row = _dict_row(cur.fetchone())
    if trip_row:
        data["trip_signin"] = _trip_signin_payload(trip_row)
        data["bag_signin"] = {
            "package_no": package_no.strip(),
            "cno_signed": int(trip_row.get("cno_signed") or 0),
            "es_context": trip_row.get("es_context") or "",
            "operation_time": trip_row.get("operation_time") or "",
        }
    return data


def refresh_bag_signin_for_package(
    package_no: str,
    *,
    record_date: Optional[str] = None,
) -> None:
    """按最新运单/轨迹重算单袋签入状态并写回袋牌表。"""
    package_no = (package_no or "").strip()
    record_date = (record_date or la_record_date()).strip()
    if not package_no:
        return
    ensure_tables()
    with get_db_connection() as conn:
        cur = conn.cursor()
        q, p = convert_placeholders(
            f"""SELECT b.*, t.actual_arrival_time
            FROM {TABLE_BAG} b
            INNER JOIN {TABLE_TRIP} t
              ON t.record_date = b.record_date AND t.task_arrival_id = b.task_arrival_id
            WHERE b.record_date = ? AND b.serial_number = ?
            LIMIT 1""",
            (record_date, package_no),
        )
        cur.execute(q, p)
        bag = _dict_row(cur.fetchone())
    if not bag:
        return
    import gofo_vehicle_arrival as gva

    if not gva.is_cno_plan_unload_point(bag.get("plan_unload_point")):
        return
    if gva.is_return_bag(package_no):
        return
    arrival = bag.get("actual_arrival_time") or ""
    signin_map = gva._compute_cno_bag_signin_map([bag], arrival)
    gva.annotate_bags_signin_status([bag], signin_map)
    synced_at = datetime.now(LA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    update_bags_signin(record_date, int(bag["task_arrival_id"]), [bag], synced_at=synced_at)
    _refresh_trip_signin_counts(
        record_date,
        int(bag["task_arrival_id"]),
        synced_at=synced_at,
    )


def _trip_signin_payload(trip: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "task_arrival_id": trip.get("task_arrival_id"),
        "transit_boxes_total": int(trip.get("transit_boxes_total") or 0),
        "cno_signed_bag_count": int(trip.get("cno_signed_bag_count") or 0),
        "bags_incomplete": 1 if trip.get("bags_incomplete") else 0,
    }


def _refresh_trip_signin_counts(
    record_date: str,
    task_arrival_id: int,
    *,
    synced_at: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """袋牌签入变化后，按库内袋牌重算车次签入指标。"""
    import gofo_vehicle_arrival as gva

    record_date = record_date.strip()
    synced_at = synced_at or datetime.now(LA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    with get_db_connection() as conn:
        cur = conn.cursor()
        q, p = convert_placeholders(
            f"""SELECT * FROM {TABLE_TRIP}
            WHERE record_date = ? AND task_arrival_id = ?
            LIMIT 1""",
            (record_date, int(task_arrival_id)),
        )
        cur.execute(q, p)
        trip = _dict_row(cur.fetchone())
        if not trip:
            return None
        q, p = convert_placeholders(
            f"""SELECT * FROM {TABLE_BAG}
            WHERE record_date = ? AND task_arrival_id = ?""",
            (record_date, int(task_arrival_id)),
        )
        cur.execute(q, p)
        bag_rows = [_dict_row(r) for r in cur.fetchall()]
    trip["transit_boxes_total"] = len(gva.filter_signin_eligible_bags(bag_rows))
    trip.update(
        gva.trip_signin_summary_from_stored_bags(
            bag_rows,
            trip.get("actual_arrival_time") or "",
        )
    )
    update_trip_signin_metrics(record_date, trip, synced_at=synced_at)
    return trip


def reconcile_trips_signin_from_stored_bags(
    record_date: str,
    trips: List[Dict[str, Any]],
    *,
    persist: bool = True,
) -> None:
    """库内已有袋牌时，按可签入箱数重算车次指标（排除 R 退件），修正装车箱数与红色不完整标记。"""
    import gofo_vehicle_arrival as gva
    from collections import defaultdict

    if not trips:
        return
    record_date = record_date.strip()
    with get_db_connection() as conn:
        cur = conn.cursor()
        q, p = convert_placeholders(
            f"""SELECT task_arrival_id, plan_unload_point, serial_number, cno_signed,
                sample_waybill_no, es_context, operation_time
            FROM {TABLE_BAG}
            WHERE record_date = ?""",
            (record_date,),
        )
        cur.execute(q, p)
        all_bags = [_dict_row(r) for r in cur.fetchall()]

    by_trip: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
    for bag in all_bags:
        try:
            aid = int(bag.get("task_arrival_id") or 0)
        except (TypeError, ValueError):
            continue
        if aid:
            by_trip[aid].append(bag)

    synced_at = datetime.now(LA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    for trip in trips:
        try:
            aid = int(trip.get("task_arrival_id") or 0)
        except (TypeError, ValueError):
            continue
        bags = by_trip.get(aid, [])
        if not bags:
            continue

        old_boxes = int(trip.get("transit_boxes_total") or 0)
        old_signed = int(trip.get("cno_signed_bag_count") or 0)
        old_inc = 1 if trip.get("bags_incomplete") else 0

        eligible_n = len(gva.filter_signin_eligible_bags(bags))
        trip["transit_boxes_total"] = eligible_n
        trip.update(
            gva.trip_signin_summary_from_stored_bags(
                bags,
                trip.get("actual_arrival_time") or "",
            )
        )

        new_signed = int(trip.get("cno_signed_bag_count") or 0)
        new_inc = 1 if trip.get("bags_incomplete") else 0
        if persist and (
            eligible_n != old_boxes
            or new_signed != old_signed
            or new_inc != old_inc
        ):
            update_trip_signin_metrics(record_date, trip, synced_at=synced_at)


def list_trip_arrival_ids(record_date: Optional[str] = None) -> set:
    record_date = (record_date or la_record_date()).strip()
    ensure_tables()
    with get_db_connection() as conn:
        cur = conn.cursor()
        q, p = convert_placeholders(
            f"SELECT task_arrival_id FROM {TABLE_TRIP} WHERE record_date = ?",
            (record_date,),
        )
        cur.execute(q, p)
        rows = cur.fetchall()
    out: set = set()
    for row in rows:
        d = _dict_row(row)
        try:
            out.add(int(d.get("task_arrival_id")))
        except (TypeError, ValueError):
            continue
    return out


def compute_day_stats_from_trips(trips: List[Dict[str, Any]]) -> Dict[str, int]:
    """当日汇总：CNO.H 签入箱数合计、装车总票数合计。"""
    signed = 0
    waybills = 0
    for t in trips or []:
        signed += int(t.get("cno_signed_bag_count") or 0)
        waybills += int(t.get("waybill_total") or 0)
    return {
        "cno_signed_boxes_total": signed,
        "total_waybills": waybills,
        "arrived_today": len(trips or []),
    }


def update_day_stats(record_date: str) -> Dict[str, int]:
    """按库内当日车次重算并写入 day 表签入箱数、总票数。"""
    record_date = record_date.strip()
    ensure_tables()
    trips = read_trips(record_date)
    stats = compute_day_stats_from_trips(trips)
    synced_at = datetime.now(LA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    with get_db_connection() as conn:
        cur = conn.cursor()
        q, p = convert_placeholders(
            f"SELECT 1 FROM {TABLE_DAY} WHERE record_date = ? LIMIT 1",
            (record_date,),
        )
        cur.execute(q, p)
        if cur.fetchone():
            q, p = convert_placeholders(
                f"""UPDATE {TABLE_DAY}
                SET arrived_today = ?,
                    cno_signed_boxes_total = ?,
                    total_waybills = ?,
                    synced_at = COALESCE(synced_at, ?)
                WHERE record_date = ?""",
                (
                    stats["arrived_today"],
                    stats["cno_signed_boxes_total"],
                    stats["total_waybills"],
                    synced_at,
                    record_date,
                ),
            )
        elif trips:
            q, p = convert_placeholders(
                f"""INSERT INTO {TABLE_DAY}
                (record_date, arrived_today, cno_signed_boxes_total, total_waybills, synced_at)
                VALUES (?, ?, ?, ?, ?)""",
                (
                    record_date,
                    stats["arrived_today"],
                    stats["cno_signed_boxes_total"],
                    stats["total_waybills"],
                    synced_at,
                ),
            )
        else:
            return stats
        cur.execute(q, p)
    return stats


def update_day_trip_count(record_date: str) -> int:
    """将 day 表 arrived_today 更新为库内当日实际车次数。"""
    record_date = record_date.strip()
    trips = read_trips(record_date)
    count = len(trips)
    ensure_tables()
    with get_db_connection() as conn:
        cur = conn.cursor()
        q, p = convert_placeholders(
            f"UPDATE {TABLE_DAY} SET arrived_today = ? WHERE record_date = ?",
            (count, record_date),
        )
        cur.execute(q, p)
    update_day_stats(record_date)
    return count


def merge_new_arrivals(
    record_date: str,
    *,
    summary: Dict[str, Any],
    trips: List[Dict[str, Any]],
    bags_by_task: Dict[int, List[Dict[str, Any]]],
    synced_at: Optional[str] = None,
) -> Dict[str, int]:
    """仅插入库中不存在的车次与袋牌；不修改/删除已有行；不触碰运单表。"""
    ensure_tables()
    synced_at = synced_at or datetime.now(LA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    record_date = record_date.strip()
    known = list_trip_arrival_ids(record_date)
    new_trips = [
        t for t in trips
        if int(t.get("task_arrival_id") or 0) not in known
    ]
    stats = {"trips_inserted": 0, "bags_inserted": 0, "trips_skipped": len(trips) - len(new_trips)}
    if not new_trips:
        return stats

    with get_db_connection() as conn:
        cur = conn.cursor()
        q, p = convert_placeholders(
            f"SELECT 1 FROM {TABLE_DAY} WHERE record_date = ? LIMIT 1",
            (record_date,),
        )
        cur.execute(q, p)
        if not cur.fetchone():
            q, p = convert_placeholders(
                f"""INSERT INTO {TABLE_DAY}
                (record_date, arrived_today, destination, date_type, center_id, synced_at)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    record_date,
                    int(summary.get("arrived_today") or 0),
                    summary.get("destination"),
                    summary.get("date_type"),
                    summary.get("center_id"),
                    synced_at,
                ),
            )
            cur.execute(q, p)

        trip_sql = f"""
            INSERT INTO {TABLE_TRIP} (
                record_date, task_arrival_id, task_no, place_of_origin, destination,
                actual_departure_time, actual_arrival_time, transit_boxes_total, waybill_total,
                line_name, license_plate_no, task_status_str,
                cno_signed_bag_count, sign_in_time, unload_duration,
                unload_duration_seconds, unload_overtime, unload_live, bags_incomplete,
                unload_start_time, unload_start_seconds, unload_timely,
                raw_json, synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        for trip in new_trips:
            q, p = convert_placeholders(
                trip_sql,
                (
                    record_date,
                    int(trip.get("task_arrival_id") or 0),
                    trip.get("task_no"),
                    trip.get("place_of_origin"),
                    trip.get("destination"),
                    trip.get("actual_departure_time"),
                    trip.get("actual_arrival_time"),
                    int(trip.get("transit_boxes_total") or 0),
                    int(trip.get("waybill_total") or 0),
                    trip.get("line_name"),
                    trip.get("license_plate_no"),
                    trip.get("task_status_str"),
                    int(trip.get("cno_signed_bag_count") or 0),
                    trip.get("sign_in_time"),
                    trip.get("unload_duration"),
                    int(trip.get("unload_duration_seconds") or 0),
                    1 if trip.get("unload_overtime") else 0,
                    1 if trip.get("unload_live") else 0,
                    1 if trip.get("bags_incomplete") else 0,
                    trip.get("unload_start_time"),
                    trip.get("unload_start_seconds"),
                    1 if trip.get("unload_timely") else 0,
                    json.dumps(trip, ensure_ascii=False, default=str),
                    synced_at,
                ),
            )
            cur.execute(q, p)
            stats["trips_inserted"] += 1

        bag_sql = f"""
            INSERT INTO {TABLE_BAG} (
                record_date, task_arrival_id, task_no, serial_number,
                load_scan_time, scan_type, load_point, plan_unload_point,
                unload_point, unload_scan_time, sample_waybill_no,
                es_context, operation_time, cno_signed, synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        new_ids = {int(t.get("task_arrival_id") or 0) for t in new_trips}
        for arrival_id, bags in bags_by_task.items():
            if int(arrival_id) not in new_ids:
                continue
            for bag in bags:
                q, p = convert_placeholders(
                    bag_sql,
                    (
                        record_date,
                        int(arrival_id),
                        bag.get("task_no"),
                        bag.get("serial_number"),
                        bag.get("load_scan_time"),
                        bag.get("scan_type"),
                        bag.get("load_point"),
                        bag.get("plan_unload_point"),
                        bag.get("unload_point"),
                        bag.get("unload_scan_time"),
                        bag.get("sample_waybill_no"),
                        bag.get("es_context"),
                        bag.get("operation_time"),
                        bag.get("cno_signed"),
                        synced_at,
                    ),
                )
                cur.execute(q, p)
                stats["bags_inserted"] += 1
    return stats


def count_trip_bags(record_date: str, task_arrival_id: int) -> int:
    record_date = record_date.strip()
    ensure_tables()
    with get_db_connection() as conn:
        cur = conn.cursor()
        q, p = convert_placeholders(
            f"""SELECT COUNT(*) AS c FROM {TABLE_BAG}
            WHERE record_date = ? AND task_arrival_id = ?""",
            (record_date, int(task_arrival_id)),
        )
        cur.execute(q, p)
        row = _dict_row(cur.fetchone())
    return int(row.get("c") or 0)


def insert_trip_bags(
    record_date: str,
    task_arrival_id: int,
    task_no: str,
    bags: List[Dict[str, Any]],
    *,
    synced_at: Optional[str] = None,
) -> int:
    """写入车次袋牌（已存在相同袋牌号则跳过）。"""
    record_date = record_date.strip()
    task_no = (task_no or "").strip()
    synced_at = synced_at or datetime.now(LA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    if not bags:
        return 0
    ensure_tables()
    inserted = 0
    with get_db_connection() as conn:
        cur = conn.cursor()
        bag_sql = f"""
            INSERT INTO {TABLE_BAG} (
                record_date, task_arrival_id, task_no, serial_number,
                load_scan_time, scan_type, load_point, plan_unload_point,
                unload_point, unload_scan_time, sample_waybill_no,
                es_context, operation_time, cno_signed, synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        for bag in bags:
            serial = str(bag.get("serial_number") or "").strip()
            if not serial:
                continue
            q, p = convert_placeholders(
                f"""SELECT 1 FROM {TABLE_BAG}
                WHERE record_date = ? AND task_arrival_id = ? AND serial_number = ?
                LIMIT 1""",
                (record_date, int(task_arrival_id), serial),
            )
            cur.execute(q, p)
            if cur.fetchone():
                continue
            q, p = convert_placeholders(
                bag_sql,
                (
                    record_date,
                    int(task_arrival_id),
                    task_no or bag.get("task_no"),
                    serial,
                    bag.get("load_scan_time"),
                    bag.get("scan_type"),
                    bag.get("load_point"),
                    bag.get("plan_unload_point"),
                    bag.get("unload_point"),
                    bag.get("unload_scan_time"),
                    bag.get("sample_waybill_no"),
                    bag.get("es_context"),
                    bag.get("operation_time"),
                    bag.get("cno_signed"),
                    synced_at,
                ),
            )
            cur.execute(q, p)
            inserted += 1
    return inserted


def ensure_trip_bags(
    task_arrival_id: int,
    *,
    record_date: Optional[str] = None,
    task_no: Optional[str] = None,
) -> Dict[str, Any]:
    """展开袋牌：库内无袋牌时从 DMS 拉取并写入，再返回袋牌列表。"""
    record_date = (record_date or la_record_date()).strip()
    task_arrival_id = int(task_arrival_id)
    ensure_tables()
    with get_db_connection() as conn:
        cur = conn.cursor()
        q, p = convert_placeholders(
            f"""SELECT * FROM {TABLE_TRIP}
            WHERE record_date = ? AND task_arrival_id = ?
            LIMIT 1""",
            (record_date, task_arrival_id),
        )
        cur.execute(q, p)
        trip = _dict_row(cur.fetchone())
    if not trip:
        raise ValueError(f"车次不存在: {task_arrival_id}")

    task_no = (task_no or trip.get("task_no") or "").strip()
    expected_boxes = int(trip.get("transit_boxes_total") or 0)
    raw_count = count_trip_bags(record_date, task_arrival_id)
    refreshed = False
    synced_at = datetime.now(LA_TZ).strftime("%Y-%m-%d %H:%M:%S")

    if raw_count == 0 and (expected_boxes > 0 or task_no):
        import gofo_vehicle_arrival as gva

        bag_data = gva.fetch_load_bag_details(task_no, task_arrival_id, enrich_tracks=False)
        bag_rows = bag_data.get("rows") or []
        for bag in bag_rows:
            bag["task_no"] = task_no
        insert_trip_bags(
            record_date,
            task_arrival_id,
            task_no,
            bag_rows,
            synced_at=synced_at,
        )
        cno_bags = gva.filter_signin_eligible_bags(bag_rows)
        with get_db_connection() as conn:
            cur = conn.cursor()
            q, p = convert_placeholders(
                f"""UPDATE {TABLE_TRIP}
                SET transit_boxes_total = ?, synced_at = ?
                WHERE record_date = ? AND task_arrival_id = ?""",
                (len(cno_bags), synced_at, record_date, task_arrival_id),
            )
            cur.execute(q, p)
        refreshed = True

    data = read_bags(
        task_arrival_id,
        record_date=record_date,
        task_no=task_no,
        actual_arrival_time=trip.get("actual_arrival_time"),
        compute_signin=not refreshed,
    )
    if data.get("rows"):
        update_bags_signin(
            record_date,
            task_arrival_id,
            data["rows"],
            synced_at=synced_at,
        )
    refreshed_trip = _refresh_trip_signin_counts(
        record_date,
        task_arrival_id,
        synced_at=synced_at,
    )
    if refreshed_trip:
        data["trip_signin"] = _trip_signin_payload(refreshed_trip)
    data["from_cache"] = not refreshed
    data["refreshed_at"] = synced_at if refreshed else data.get("fetched_at", "")
    return data


def update_trip_signin_metrics(
    record_date: str,
    trip: Dict[str, Any],
    *,
    synced_at: Optional[str] = None,
) -> None:
    """仅更新车次签入相关指标（不重写袋牌/运单）。"""
    ensure_tables()
    record_date = record_date.strip()
    synced_at = synced_at or datetime.now(LA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    arrival_id = int(trip.get("task_arrival_id") or 0)
    if not arrival_id:
        return
    with get_db_connection() as conn:
        cur = conn.cursor()
        q, p = convert_placeholders(
            f"""UPDATE {TABLE_TRIP} SET
                transit_boxes_total = ?,
                cno_signed_bag_count = ?,
                sign_in_time = ?,
                unload_duration = ?,
                unload_duration_seconds = ?,
                unload_overtime = ?,
                bags_incomplete = ?,
                unload_start_time = ?,
                unload_start_seconds = ?,
                unload_timely = ?,
                synced_at = ?
            WHERE record_date = ? AND task_arrival_id = ?""",
            (
                int(trip.get("transit_boxes_total") or 0),
                int(trip.get("cno_signed_bag_count") or 0),
                trip.get("sign_in_time"),
                trip.get("unload_duration"),
                int(trip.get("unload_duration_seconds") or 0),
                1 if trip.get("unload_overtime") else 0,
                1 if trip.get("bags_incomplete") else 0,
                trip.get("unload_start_time"),
                trip.get("unload_start_seconds"),
                1 if trip.get("unload_timely") else 0,
                synced_at,
                record_date,
                arrival_id,
            ),
        )
        cur.execute(q, p)


def save_day_snapshot(
    record_date: str,
    *,
    summary: Dict[str, Any],
    trips: List[Dict[str, Any]],
    bags_by_task: Dict[int, List[Dict[str, Any]]],
    waybills_by_package: Dict[str, List[Dict[str, Any]]],
    synced_at: Optional[str] = None,
    sync_waybills: bool = True,
) -> None:
    """整日快照：先删后插。sync_waybills=False 时保留已有运单表。"""
    ensure_tables()
    synced_at = synced_at or datetime.now(LA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    with get_db_connection() as conn:
        cur = conn.cursor()
        _delete_day(cur, record_date, include_waybills=sync_waybills)

        q, p = convert_placeholders(
            f"""INSERT INTO {TABLE_DAY}
            (record_date, arrived_today, destination, date_type, center_id, synced_at)
            VALUES (?, ?, ?, ?, ?, ?)""",
            (
                record_date,
                int(summary.get("arrived_today") or 0),
                summary.get("destination"),
                summary.get("date_type"),
                summary.get("center_id"),
                synced_at,
            ),
        )
        cur.execute(q, p)

        trip_sql = f"""
            INSERT INTO {TABLE_TRIP} (
                record_date, task_arrival_id, task_no, place_of_origin, destination,
                actual_departure_time, actual_arrival_time, transit_boxes_total, waybill_total,
                line_name, license_plate_no, task_status_str,
                cno_signed_bag_count, sign_in_time, unload_duration,
                unload_duration_seconds, unload_overtime, unload_live, bags_incomplete,
                unload_start_time, unload_start_seconds, unload_timely,
                raw_json, synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        for trip in trips:
            q, p = convert_placeholders(
                trip_sql,
                (
                    record_date,
                    int(trip.get("task_arrival_id") or 0),
                    trip.get("task_no"),
                    trip.get("place_of_origin"),
                    trip.get("destination"),
                    trip.get("actual_departure_time"),
                    trip.get("actual_arrival_time"),
                    int(trip.get("transit_boxes_total") or 0),
                    int(trip.get("waybill_total") or 0),
                    trip.get("line_name"),
                    trip.get("license_plate_no"),
                    trip.get("task_status_str"),
                    int(trip.get("cno_signed_bag_count") or 0),
                    trip.get("sign_in_time"),
                    trip.get("unload_duration"),
                    int(trip.get("unload_duration_seconds") or 0),
                    1 if trip.get("unload_overtime") else 0,
                    1 if trip.get("unload_live") else 0,
                    1 if trip.get("bags_incomplete") else 0,
                    trip.get("unload_start_time"),
                    trip.get("unload_start_seconds"),
                    1 if trip.get("unload_timely") else 0,
                    json.dumps(trip, ensure_ascii=False, default=str),
                    synced_at,
                ),
            )
            cur.execute(q, p)

        bag_sql = f"""
            INSERT INTO {TABLE_BAG} (
                record_date, task_arrival_id, task_no, serial_number,
                load_scan_time, scan_type, load_point, plan_unload_point,
                unload_point, unload_scan_time, sample_waybill_no,
                es_context, operation_time, cno_signed, synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        for arrival_id, bags in bags_by_task.items():
            for bag in bags:
                q, p = convert_placeholders(
                    bag_sql,
                    (
                        record_date,
                        int(arrival_id),
                        bag.get("task_no"),
                        bag.get("serial_number"),
                        bag.get("load_scan_time"),
                        bag.get("scan_type"),
                        bag.get("load_point"),
                        bag.get("plan_unload_point"),
                        bag.get("unload_point"),
                        bag.get("unload_scan_time"),
                        bag.get("sample_waybill_no"),
                        bag.get("es_context"),
                        bag.get("operation_time"),
                        bag.get("cno_signed"),
                        synced_at,
                    ),
                )
                cur.execute(q, p)

        if sync_waybills:
            for package_no, rows in waybills_by_package.items():
                if rows:
                    _insert_waybill_rows(cur, record_date, package_no, rows, synced_at)


        cur.execute(q, p)


def update_bags_signin(
    record_date: str,
    task_arrival_id: int,
    bags: List[Dict[str, Any]],
    *,
    synced_at: Optional[str] = None,
) -> None:
    """更新袋牌签入标记（repair 用）。"""
    ensure_tables()
    record_date = record_date.strip()
    synced_at = synced_at or datetime.now(LA_TZ).strftime("%Y-%m-%d %H:%M:%S")
    with get_db_connection() as conn:
        cur = conn.cursor()
        for bag in bags:
            q, p = convert_placeholders(
                f"""UPDATE {TABLE_BAG} SET
                    cno_signed = ?,
                    sample_waybill_no = ?,
                    es_context = ?,
                    operation_time = ?,
                    synced_at = ?
                WHERE record_date = ? AND task_arrival_id = ? AND serial_number = ?""",
                (
                    bag.get("cno_signed"),
                    bag.get("sample_waybill_no"),
                    bag.get("es_context"),
                    bag.get("operation_time"),
                    synced_at,
                    record_date,
                    int(task_arrival_id),
                    bag.get("serial_number"),
                ),
            )
            cur.execute(q, p)


def _dict_row(row) -> Dict[str, Any]:
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    return dict(row)


def read_summary(record_date: Optional[str] = None) -> Dict[str, Any]:
    record_date = (record_date or la_record_date()).strip()
    ensure_tables()
    with get_db_connection() as conn:
        cur = conn.cursor()
        q, p = convert_placeholders(
            f"SELECT * FROM {TABLE_DAY} WHERE record_date = ?",
            (record_date,),
        )
        cur.execute(q, p)
        row = _dict_row(cur.fetchone())
    if not row:
        trips = read_trips(record_date)
        live = compute_day_stats_from_trips(trips) if trips else {}
        return {
            "record_date": record_date,
            "arrived_today": live.get("arrived_today", 0),
            "cno_signed_boxes_total": live.get("cno_signed_boxes_total", 0),
            "total_waybills": live.get("total_waybills", 0),
            "destination": "",
            "date_type": "",
            "center_id": 0,
            "fetched_at": "",
            "synced_at": "",
            "empty": not trips,
        }
    return {
        "record_date": row.get("record_date"),
        "arrived_today": row.get("arrived_today") or 0,
        "cno_signed_boxes_total": int(row.get("cno_signed_boxes_total") or 0),
        "total_waybills": int(row.get("total_waybills") or 0),
        "destination": row.get("destination") or "",
        "date_type": row.get("date_type") or "",
        "center_id": row.get("center_id") or 0,
        "fetched_at": row.get("synced_at") or "",
        "synced_at": row.get("synced_at") or "",
        "empty": False,
    }


def read_trips(record_date: Optional[str] = None) -> List[Dict[str, Any]]:
    record_date = (record_date or la_record_date()).strip()
    ensure_tables()
    with get_db_connection() as conn:
        cur = conn.cursor()
        q, p = convert_placeholders(
            f"""SELECT * FROM {TABLE_TRIP}
            WHERE record_date = ?
            ORDER BY actual_arrival_time DESC, task_no""",
            (record_date,),
        )
        cur.execute(q, p)
        rows = [_dict_row(r) for r in cur.fetchall()]
    return rows


def read_bags(
    task_arrival_id: int,
    *,
    record_date: Optional[str] = None,
    task_no: Optional[str] = None,
    actual_arrival_time: Optional[str] = None,
    compute_signin: bool = True,
) -> Dict[str, Any]:
    record_date = (record_date or la_record_date()).strip()
    ensure_tables()
    with get_db_connection() as conn:
        cur = conn.cursor()
        q, p = convert_placeholders(
            f"""SELECT * FROM {TABLE_BAG}
            WHERE record_date = ? AND task_arrival_id = ?
            ORDER BY load_scan_time DESC, serial_number""",
            (record_date, int(task_arrival_id)),
        )
        cur.execute(q, p)
        rows = [_dict_row(r) for r in cur.fetchall()]
        if actual_arrival_time is None:
            q2, p2 = convert_placeholders(
                f"""SELECT actual_arrival_time FROM {TABLE_TRIP}
                WHERE record_date = ? AND task_arrival_id = ?
                LIMIT 1""",
                (record_date, int(task_arrival_id)),
            )
            cur.execute(q2, p2)
            trip_row = _dict_row(cur.fetchone())
            actual_arrival_time = trip_row.get("actual_arrival_time") or ""
    import gofo_vehicle_arrival as gva

    rows = gva.filter_cno_plan_unload_bags(rows)
    eligible = gva.filter_signin_eligible_bags(rows)
    needs_signin = any(
        gva.is_cno_plan_unload_point(r.get("plan_unload_point"))
        and not gva.is_return_bag(r.get("serial_number"))
        and r.get("cno_signed") is None
        for r in rows
    )
    if compute_signin and needs_signin and actual_arrival_time:
        signin_map = gva._compute_cno_bag_signin_map(eligible, actual_arrival_time)
        gva.annotate_bags_signin_status(rows, signin_map)
    unsigned = gva.unsigned_cno_bag_serials(rows)
    rows.sort(
        key=lambda r: (
            0
            if int(r.get("cno_signed") or 0) == 0
            and not gva.is_return_bag(r.get("serial_number"))
            else 1,
            r.get("load_scan_time") or "",
            r.get("serial_number") or "",
        )
    )
    tn = task_no or (rows[0].get("task_no") if rows else "")
    return {
        "record_date": record_date,
        "task_no": tn,
        "task_arrival_id": int(task_arrival_id),
        "total": len(rows),
        "unsigned_count": len(unsigned),
        "unsigned_serials": unsigned,
        "rows": rows,
        "fetched_at": rows[0].get("synced_at") if rows else "",
    }


def read_package_waybills(
    package_no: str,
    *,
    record_date: Optional[str] = None,
) -> Dict[str, Any]:
    package_no = (package_no or "").strip()
    record_date = (record_date or la_record_date()).strip()
    ensure_tables()
    with get_db_connection() as conn:
        cur = conn.cursor()
        q, p = convert_placeholders(
            f"""SELECT * FROM {TABLE_WAYBILL}
            WHERE record_date = ? AND package_no = ?
            ORDER BY waybill_no""",
            (record_date, package_no),
        )
        cur.execute(q, p)
        rows = [_dict_row(r) for r in cur.fetchall()]
    return {
        "record_date": record_date,
        "package_no": package_no,
        "total": len(rows),
        "rows": rows,
        "fetched_at": rows[0].get("synced_at") if rows else "",
    }


def read_waybill_track(
    waybill_no: str,
    *,
    record_date: Optional[str] = None,
) -> Dict[str, Any]:
    waybill_no = (waybill_no or "").strip()
    record_date = (record_date or la_record_date()).strip()
    ensure_tables()
    with get_db_connection() as conn:
        cur = conn.cursor()
        q, p = convert_placeholders(
            f"""SELECT * FROM {TABLE_WAYBILL}
            WHERE record_date = ? AND waybill_no = ?
            ORDER BY package_no
            LIMIT 1""",
            (record_date, waybill_no),
        )
        cur.execute(q, p)
        row = _dict_row(cur.fetchone())
    if not row:
        return {
            "waybill_no": waybill_no,
            "es_context": "",
            "operation_time": "",
            "tracks": [],
            "fetched_at": "",
        }
    ev = {
        "es_context": row.get("es_context") or "",
        "operation_time": row.get("operation_time") or "",
    }
    tracks = [ev] if ev.get("es_context") or ev.get("operation_time") else []
    return {
        "waybill_no": waybill_no,
        "es_context": ev["es_context"],
        "operation_time": ev["operation_time"],
        "tracks": tracks,
        "fetched_at": row.get("synced_at") or "",
    }


def compute_timely_rate(trips: List[Dict[str, Any]]) -> Dict[str, Any]:
    eligible = [t for t in trips if int(t.get("transit_boxes_total") or 0) > 0]
    total = len(eligible)
    if not total:
        return {"timely_trips": 0, "total_trips": 0, "timely_rate_pct": 0.0}
    timely = sum(1 for t in eligible if int(t.get("unload_timely") or 0) == 1)
    return {
        "timely_trips": timely,
        "total_trips": total,
        "timely_rate_pct": round(timely / total * 100, 1),
    }


def read_page(record_date: Optional[str] = None) -> Dict[str, Any]:
    la_today = la_record_date()
    record_date = (record_date or la_today).strip()
    summary = read_summary(record_date)
    trips = read_trips(record_date)
    import gofo_vehicle_arrival as gva

    reconcile_trips_signin_from_stored_bags(record_date, trips)
    for trip in trips:
        gva.apply_trip_unload_display(trip)
    trip_count = len(trips)
    summary["arrived_today"] = trip_count
    if trip_count > 0:
        summary["empty"] = False
    summary["rows"] = trips
    summary["total"] = trip_count
    summary.update(compute_timely_rate(trips))
    summary.update(compute_day_stats_from_trips(trips))
    if trip_count == 0:
        stored = read_summary(record_date)
        if int(stored.get("cno_signed_boxes_total") or 0) or int(stored.get("total_waybills") or 0):
            summary["cno_signed_boxes_total"] = stored.get("cno_signed_boxes_total", 0)
            summary["total_waybills"] = stored.get("total_waybills", 0)
    summary["la_today"] = la_today
    summary["available_dates"] = list_record_dates()
    return summary
