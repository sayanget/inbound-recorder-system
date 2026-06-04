"""
CNO 劳务公司 Sorter 分时产能（与 sync_cno_narrowbelt_hourly 同源 operatelog scan 217）。

- 仅统计操作员名匹配「{劳务公司} Sorter {账号}」（排除 CNO 直线窄带分拣机等设备名）。
- GF 公司：Sorter 编号 10/38/39/40 为计时 (hourly)，2/4/5 为计件 (piece)。
- CNO.H 公司：Sorter 06 为计时；其余 Sorter 为计件。
- DJ 公司：操作员「DJ storing 01」为计时组（非 Sorter 命名）。
- 其余劳务公司 Sorter 均为计件。
- 由窄带同步在同一时间窗拉取日志后调用 persist_hour_slot_from_rows，不重复请求 Gofo。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

PAY_TYPE_PIECE = "piece"
PAY_TYPE_HOURLY = "hourly"

_GF_HOURLY_ACCOUNTS = frozenset({"10", "38", "39", "40"})
_GF_PIECE_ACCOUNTS = frozenset({"2", "4", "5"})
# 与 _norm_sorter_account 一致：「06」规范为「6」
_CNOH_HOURLY_ACCOUNTS = frozenset({"6"})

_LABOR_SORTER_RE = re.compile(r"^(.+?)\s+Sorter\s+(\S+)\s*$", re.IGNORECASE)

_MACHINE_MARKERS = (
    "直线窄带",
    "窄带分拣机",
    "CNO直线",
    "分拣机-",
    "DWS",
    "AUTOSORT",
)

# 操作员全名（小写）→ (公司, 账号标签)；计薪类型由 classify_labor_pay_type 判定
_EXTRA_LABOR_OPERATORS = {
    "dj storing 01": ("DJ", "storing 01"),
}


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


def parse_labor_operator(name: Any) -> Optional[Tuple[str, str]]:
    """解析劳务操作员：Sorter 命名 + 额外计时组（如 DJ storing 01）。"""
    if not name or not isinstance(name, str):
        return None
    s = name.strip()
    if not s:
        return None
    extra = _EXTRA_LABOR_OPERATORS.get(s.lower())
    if extra:
        return extra
    return parse_labor_sorter_operator(name)


def _norm_sorter_account(account: str) -> str:
    s = (account or "").strip()
    if s.isdigit():
        return str(int(s))
    return s


def _is_gf_company(company: str) -> bool:
    return (company or "").strip().upper() == "GF"


def _is_dj_company(company: str) -> bool:
    return (company or "").strip().upper() == "DJ"


def _is_cno_h_company(company: str) -> bool:
    c = (company or "").strip().upper()
    return c in ("CNO.H", "CNOH") or c.replace(".", "") == "CNOH"


def classify_labor_pay_type(company: str, account: str) -> str:
    """GF：10/38/39/40 计时，2/4/5 计件；CNO.H：06 计时；DJ storing 01 计时；其余计件。"""
    if _is_dj_company(company) and (account or "").strip().lower() == "storing 01":
        return PAY_TYPE_HOURLY
    acc = _norm_sorter_account(account)
    if _is_gf_company(company):
        if acc in _GF_HOURLY_ACCOUNTS:
            return PAY_TYPE_HOURLY
        if acc in _GF_PIECE_ACCOUNTS:
            return PAY_TYPE_PIECE
        return PAY_TYPE_PIECE
    if _is_cno_h_company(company) and acc in _CNOH_HOURLY_ACCOUNTS:
        return PAY_TYPE_HOURLY
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
        parsed = parse_labor_operator(op)
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
        parsed = parse_labor_operator(op)
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
        _persist_group_hourly_slots(
            cur, record_date, time_slot, acct_raw, acct_dedup, acct_keys, synced_at
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "labor_sorter_keys": len(all_keys),
        "labor_account_keys": len(acct_keys),
        "counts": {f"{c}|{p}": counts_raw.get((c, p), 0) for c, p in all_keys},
    }


def _persist_group_hourly_slots(
    cur,
    record_date: str,
    time_slot: str,
    acct_raw: Dict[Tuple[str, str, str], int],
    acct_dedup: Dict[Tuple[str, str, str], int],
    acct_keys: set,
    synced_at: str,
) -> None:
    """写入 cno_labor_group_hourly：按运营锚点日 + 统计窗口 + 组号 + 整点。"""
    from single_app import la_record_slot_to_operating_anchor

    slot_norm = (time_slot or "").strip()
    if len(slot_norm) >= 5 and slot_norm[2] == ":":
        slot_norm = f"{int(slot_norm[:2]):02d}:{slot_norm[3:5]}"
    for window_mode in ("calendar", "business", "seventeen"):
        anchor = la_record_slot_to_operating_anchor(
            record_date, slot_norm, window_mode
        )
        if not anchor:
            continue
        for company, account, pay_type in acct_keys:
            n_raw = int(acct_raw.get((company, account, pay_type), 0))
            n_ded = int(acct_dedup.get((company, account, pay_type), 0))
            cur.execute(
                """
                INSERT INTO cno_labor_group_hourly
                    (anchor_date, stats_window, time_slot, company_code, group_no,
                     pay_type, pieces, pieces_deduped, record_date_la, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(anchor_date, stats_window, time_slot, company_code, group_no)
                DO UPDATE SET
                    pay_type = excluded.pay_type,
                    pieces = excluded.pieces,
                    pieces_deduped = excluded.pieces_deduped,
                    record_date_la = excluded.record_date_la,
                    synced_at = excluded.synced_at
                """,
                (
                    anchor,
                    window_mode,
                    slot_norm,
                    company,
                    account,
                    pay_type,
                    n_raw,
                    n_ded,
                    record_date,
                    synced_at,
                ),
            )
