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
    """先读库；无运单时从 GoFO 拉取并写入。已有运单则只读库，不刷新轨迹。"""
    record_date = (record_date or la_record_date()).strip()
    data = read_package_waybills(package_no, record_date=record_date)
    if data.get("rows"):
        data["from_cache"] = True
        return data
    import gofo_vehicle_arrival as gva

    fetched = gva.fetch_package_waybill_details(package_no)
    rows = fetched.get("rows") or []
    if rows:
        upsert_package_waybills(package_no, rows, record_date=record_date)
        data = read_package_waybills(package_no, record_date=record_date)
    data["from_cache"] = False
    return data


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
                es_context, operation_time, synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        synced_at,
                    ),
                )
                cur.execute(q, p)
                stats["bags_inserted"] += 1
    return stats


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
                es_context, operation_time, synced_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        synced_at,
                    ),
                )
                cur.execute(q, p)

        if sync_waybills:
            for package_no, rows in waybills_by_package.items():
                if rows:
                    _insert_waybill_rows(cur, record_date, package_no, rows, synced_at)


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
        return {
            "record_date": record_date,
            "arrived_today": 0,
            "destination": "",
            "date_type": "",
            "center_id": 0,
            "fetched_at": "",
            "synced_at": "",
            "empty": True,
        }
    return {
        "record_date": row.get("record_date"),
        "arrived_today": row.get("arrived_today") or 0,
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
    import gofo_vehicle_arrival as gva

    rows = gva.filter_cno_plan_unload_bags(rows)
    tn = task_no or (rows[0].get("task_no") if rows else "")
    return {
        "record_date": record_date,
        "task_no": tn,
        "task_arrival_id": int(task_arrival_id),
        "total": len(rows),
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
    record_date = (record_date or la_record_date()).strip()
    summary = read_summary(record_date)
    trips = read_trips(record_date)
    if summary.get("empty") and trips:
        summary["arrived_today"] = len(trips)
        summary["empty"] = False
    summary["rows"] = trips
    summary["total"] = len(trips)
    summary.update(compute_timely_rate(trips))
    return summary
