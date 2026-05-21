"""
CNO 劳务公司 Sorter 分时产能（与 sync_cno_narrowbelt_hourly 同源 operatelog scan 217）。

- 仅统计操作员名匹配「{劳务公司} Sorter {账号}」（排除 CNO 直线窄带分拣机等设备名）。
- GF 公司：Sorter 编号 10/38/39/40 为计时 (hourly)，2/4/5 为计件 (piece)；其余劳务公司均为计件。
- 由窄带同步在同一时间窗拉取日志后调用 persist_hour_slot_from_rows，不重复请求 Gofo。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

PAY_TYPE_PIECE = "piece"
PAY_TYPE_HOURLY = "hourly"

_GF_HOURLY_ACCOUNTS = frozenset({"10", "38", "39", "40"})
_GF_PIECE_ACCOUNTS = frozenset({"2", "4", "5"})

_LABOR_SORTER_RE = re.compile(r"^(.+?)\s+Sorter\s+(\S+)\s*$", re.IGNORECASE)

_MACHINE_MARKERS = (
    "直线窄带",
    "窄带分拣机",
    "CNO直线",
    "分拣机-",
    "DWS",
    "AUTOSORT",
)


def parse_labor_sorter_operator(name: Any) -> Optional[Tuple[str, str]]:
    """解析「XX Sorter xx」→ (company, account)；非劳务 Sorter 返回 None。"""
    if not name or not isinstance(name, str):
        return None
    s = name.strip()
    if not s or " Sorter " not in s:
        return None
    for mk in _MACHINE_MARKERS:
        if mk in s:
            return None
    if "CNO直线" in s.upper().replace(" ", ""):
        return None
    m = _LABOR_SORTER_RE.match(s)
    if not m:
        return None
    company = m.group(1).strip()
    account = m.group(2).strip()
    if not company or not account:
        return None
    if company.upper().startswith("CNO直线"):
        return None
    return company, account


def _norm_sorter_account(account: str) -> str:
    s = (account or "").strip()
    if s.isdigit():
        return str(int(s))
    return s


def _is_gf_company(company: str) -> bool:
    return (company or "").strip().upper() == "GF"


def classify_labor_pay_type(company: str, account: str) -> str:
    """GF：10/38/39/40 计时，2/4/5 计件；其余公司均为计件。"""
    if not _is_gf_company(company):
        return PAY_TYPE_PIECE
    acc = _norm_sorter_account(account)
    if acc in _GF_HOURLY_ACCOUNTS:
        return PAY_TYPE_HOURLY
    if acc in _GF_PIECE_ACCOUNTS:
        return PAY_TYPE_PIECE
    return PAY_TYPE_PIECE


def counts_by_labor_company_both(
    rows: List[Dict[str, Any]],
) -> Tuple[Dict[Tuple[str, str], int], Dict[Tuple[str, str], int]]:
    """返回 ((company, pay_type) -> 逐条), ((company, pay_type) -> 去重)。"""
    raw: Dict[Tuple[str, str], int] = {}
    dedup: Dict[Tuple[str, str], int] = {}
    seen: set = set()
    for r in rows:
        op = r.get("createByName")
        parsed = parse_labor_sorter_operator(op)
        if not parsed:
            continue
        company, account = parsed
        pay_type = classify_labor_pay_type(company, account)
        key = (company, pay_type)
        raw[key] = raw.get(key, 0) + 1
        waybill = r.get("waybillNo") or ""
        st = r.get("scanTypeStr") or ""
        dkey = (waybill, st, op)
        if dkey in seen:
            continue
        seen.add(dkey)
        dedup[key] = dedup.get(key, 0) + 1
    return raw, dedup


def counts_by_labor_account_both(
    rows: List[Dict[str, Any]],
) -> Tuple[Dict[Tuple[str, str, str], int], Dict[Tuple[str, str, str], int]]:
    """按 (公司, 账号, 计薪类型) 计数；相同 XX+xx 为同一组。"""
    raw: Dict[Tuple[str, str, str], int] = {}
    dedup: Dict[Tuple[str, str, str], int] = {}
    seen: set = set()
    for r in rows:
        op = r.get("createByName")
        parsed = parse_labor_sorter_operator(op)
        if not parsed:
            continue
        company, account = parsed
        pay_type = classify_labor_pay_type(company, account)
        key = (company, account, pay_type)
        raw[key] = raw.get(key, 0) + 1
        waybill = r.get("waybillNo") or ""
        st = r.get("scanTypeStr") or ""
        dkey = (waybill, st, op)
        if dkey in seen:
            continue
        seen.add(dkey)
        dedup[key] = dedup.get(key, 0) + 1
    return raw, dedup


def persist_hour_slot_from_rows(
    record_date: str,
    time_slot: str,
    rows: List[Dict[str, Any]],
    synced_at: str,
) -> Dict[str, Any]:
    """将单小时 operatelog 行写入 cno_labor_sorter_hourly。"""
    from single_app import get_db

    counts_raw, counts_dedup = counts_by_labor_company_both(rows)
    acct_raw, acct_dedup = counts_by_labor_account_both(rows)
    all_keys = set(counts_raw.keys()) | set(counts_dedup.keys())
    acct_keys = set(acct_raw.keys()) | set(acct_dedup.keys())

    conn = get_db()
    cur = conn.cursor()
    try:
        for company, pay_type in all_keys:
            n_raw = int(counts_raw.get((company, pay_type), 0))
            n_ded = int(counts_dedup.get((company, pay_type), 0))
            cur.execute(
                """
                INSERT INTO cno_labor_sorter_hourly
                    (record_date, time_slot, company_code, pay_type, pieces, pieces_deduped, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(record_date, time_slot, company_code, pay_type) DO UPDATE SET
                    pieces = excluded.pieces,
                    pieces_deduped = excluded.pieces_deduped,
                    synced_at = excluded.synced_at
                """,
                (record_date, time_slot, company, pay_type, n_raw, n_ded, synced_at),
            )
        for company, account, pay_type in acct_keys:
            n_raw = int(acct_raw.get((company, account, pay_type), 0))
            n_ded = int(acct_dedup.get((company, account, pay_type), 0))
            cur.execute(
                """
                INSERT INTO cno_labor_sorter_account_hourly
                    (record_date, time_slot, company_code, account_label, pay_type,
                     pieces, pieces_deduped, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(record_date, time_slot, company_code, account_label) DO UPDATE SET
                    pay_type = excluded.pay_type,
                    pieces = excluded.pieces,
                    pieces_deduped = excluded.pieces_deduped,
                    synced_at = excluded.synced_at
                """,
                (
                    record_date,
                    time_slot,
                    company,
                    account,
                    pay_type,
                    n_raw,
                    n_ded,
                    synced_at,
                ),
            )
        conn.commit()
    finally:
        conn.close()

    return {
        "labor_sorter_keys": len(all_keys),
        "labor_account_keys": len(acct_keys),
        "counts": {f"{c}|{p}": counts_raw.get((c, p), 0) for c, p in all_keys},
    }
