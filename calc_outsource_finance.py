import os
import re
import pytz
from collections import defaultdict
from datetime import datetime, timedelta

import requests

try:
    from database import USE_POSTGRES, DATABASE_URL, get_sqlite_db_path
except ImportError:
    USE_POSTGRES = False
    DATABASE_URL = None

    def get_sqlite_db_path():
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'inbound.db')

# --- 飞书 API 配置 ---
FEISHU_APP_ID = os.getenv('FEISHU_APP_ID', 'cli_a9fc1c1c0bb8dbcb')
FEISHU_APP_SECRET = os.getenv('FEISHU_APP_SECRET', 'XeStEZgDlQQUnUU93w1d3emYSdMSfiq6')
SPREADSHEET_TOKEN_DEFAULT = 'FYWYsrb70ho1xEtq9unceocwnSf'
SHEET_ID_DEFAULT = 'V2dsq4'

# 与 single_app 一致：入库实到件数 = (录入 − excluded_pieces) × 系数；53+G 为 0
INBOUND_PIECES_ACTUAL_FACTOR = float(os.environ.get("INBOUND_PIECES_ACTUAL_FACTOR", "0.76"))


def _open_labor_db():
    """与 single_app 使用同一数据库（SQLite 或 PostgreSQL）。"""
    if USE_POSTGRES and DATABASE_URL:
        import psycopg2
        from psycopg2.extras import DictCursor
        return psycopg2.connect(DATABASE_URL, cursor_factory=DictCursor), True
    import sqlite3
    conn = sqlite3.connect(get_sqlite_db_path(), timeout=30)
    conn.row_factory = sqlite3.Row
    return conn, False


def _q(sql: str, is_pg: bool) -> str:
    return sql.replace('?', '%s') if is_pg else sql


def _tbl(is_pg: bool) -> str:
    return 'daily_cost_summary'


def _cols(is_pg: bool) -> dict:
    if is_pg:
        return {
            'date': 'record_date',
            'agency': 'agency_name',
            'hourly': 'hourly_cost_usd',
            'piece': 'piece_cost_usd',
            'total': 'total_cost_usd',
            'headcount': 'headcount',
            'total_pieces': 'total_pieces',
            'corrected_pieces': 'corrected_pieces',
        }
    return {
        'date': 'Record_Date',
        'agency': 'Agency_Name',
        'hourly': 'Hourly_Cost_USD',
        'piece': 'Piece_Cost_USD',
        'total': 'Total_Cost_USD',
        'headcount': 'Headcount',
        'total_pieces': 'Total_Pieces',
        'corrected_pieces': 'Corrected_Pieces',
    }


def _ensure_daily_cost_table(cur, is_pg: bool) -> None:
    c = _cols(is_pg)
    if is_pg:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {_tbl(is_pg)} (
                {c['date']} TEXT NOT NULL,
                {c['agency']} TEXT NOT NULL,
                {c['hourly']} REAL DEFAULT 0,
                {c['piece']} REAL DEFAULT 0,
                {c['total']} REAL DEFAULT 0,
                {c['headcount']} INTEGER DEFAULT 0,
                {c['total_pieces']} INTEGER DEFAULT 0,
                {c['corrected_pieces']} INTEGER DEFAULT 0,
                PRIMARY KEY ({c['date']}, {c['agency']})
            )
        """)
    else:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {_tbl(is_pg)} (
                {c['date']} TEXT NOT NULL,
                {c['agency']} TEXT NOT NULL,
                {c['hourly']} REAL DEFAULT 0,
                {c['piece']} REAL DEFAULT 0,
                {c['total']} REAL DEFAULT 0,
                {c['headcount']} INTEGER DEFAULT 0,
                {c['total_pieces']} INTEGER DEFAULT 0,
                {c['corrected_pieces']} INTEGER DEFAULT 0,
                PRIMARY KEY ({c['date']}, {c['agency']})
            )
        """)


def _insert_ignore_daily_row(cur, is_pg: bool, rdate: str, agency: str) -> None:
    c = _cols(is_pg)
    t = _tbl(is_pg)
    if is_pg:
        cur.execute(
            _q(
                f"INSERT INTO {t} ({c['date']}, {c['agency']}) VALUES (?, ?) "
                f"ON CONFLICT ({c['date']}, {c['agency']}) DO NOTHING",
                is_pg,
            ),
            (rdate, agency),
        )
    else:
        cur.execute(
            _q(f"INSERT OR IGNORE INTO {t} ({c['date']}, {c['agency']}) VALUES (?, ?)", is_pg),
            (rdate, agency),
        )


def _parse_feishu_sheet_link(link: str):
    """解析飞书表格链接，返回 (spread_token, sheet_id) 或 None。"""
    if not link:
        return None
    token_m = re.search(r'(?:sheets|wiki)/([a-zA-Z0-9]+)', link, re.I)
    if not token_m:
        return None
    sheet_m = re.search(r'[?&]sheet(?:Id)?=([a-zA-Z0-9]+)', link, re.I)
    if not sheet_m:
        return None
    return token_m.group(1), sheet_m.group(1)


def get_feishu_tenant_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    payload = {
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    }
    response = requests.post(url, json=payload)
    response.raise_for_status()
    return response.json().get('tenant_access_token')

def fetch_feishu_sheet_data(token, spread_token, sheet_id):
    range_str = f"{sheet_id}!A:Z"
    url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spread_token}/values/{range_str}?valueRenderOption=ToString"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json().get('data', {}).get('valueRange', {}).get('values', [])


def _norm_sheet_cell(cell) -> str:
    if cell is None:
        return ""
    return str(cell).strip().replace("\ufeff", "").strip()


def _is_name_header_cell(cell) -> bool:
    u = _norm_sheet_cell(cell).upper()
    return u in ("NAME", "姓名", "名字", "员工", "员工姓名", "OPERATOR", "操作员")


def _find_labor_rate_col(row):
    """返回 (列索引, 'Hourly'|'Piece')；列名不区分大小写，支持中英文。"""
    for i, col in enumerate(row):
        c = _norm_sheet_cell(col).lower().replace("_", " ")
        if c in ("hourly rate", "hourlyrate", "时薪", "小时费率", "小时工资", "hourly"):
            return i, "Hourly"
        if c in ("price", "piece rate", "piecerate", "单价", "计件单价", "件价", "piece"):
            return i, "Piece"
    return -1, None


def _find_labor_agency_col(row) -> int:
    for i, col in enumerate(row):
        c = _norm_sheet_cell(col).lower()
        if c in ("agency", "agence", "company", "代理商", "劳务公司", "公司", "vendor"):
            return i
    return -1


def _find_labor_name_col(row) -> int:
    """姓名列索引（新表 A 列为考勤 ID 时 NAME 在 B 列）。"""
    for i, col in enumerate(row):
        if _is_name_header_cell(col):
            return i
    return 0


_LABOR_NON_DATE_HEADERS = frozenset({
    "total hours", "overtime", "cost", "hourly rate", "price",
    "total cost aft tax", "total cost", "state", "job", "name",
    "agency", "agence", "company", "站点/组别", "站点/枢纽", "站点", "枢纽",
    "关联oa 流程单号", "考勤id", "考勤 id",
})


def _is_labor_date_header(val) -> bool:
    s = _norm_sheet_cell(val)
    if not s:
        return False
    low = s.lower()
    if low in _LABOR_NON_DATE_HEADERS:
        return False
    if "total" in low and "hour" in low:
        return False
    if "hourly" in low and "rate" in low:
        return False
    if "/" in s and re.search(r"\d", s):
        return True
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return True
    if re.match(r"^\d{1,2}-\d{1,2}(-\d{2,4})?$", s):
        return True
    return False


def _parse_sheet_number(val) -> float:
    """工时/费率：支持 11.50、11,50、$20.00。"""
    s = _norm_sheet_cell(val).replace(",", ".")
    for ch in ("$", "￥", "¥", " "):
        s = s.replace(ch, "")
    if not s or s in ("-", "—", "–"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        pass
    if s.replace(".", "", 1).isdigit():
        return float(s)
    return 0.0


def _parse_labor_header_row(row):
    """
    识别排班表头行：含 NAME/姓名 与 Hourly Rate/Price（支持左侧新增考勤 ID 列）。
    返回 (mode, rate_idx, agency_idx, name_idx, date_cols) 或 None。
    """
    if not row:
        return None
    name_idx = _find_labor_name_col(row)
    if not _is_name_header_cell(row[name_idx] if name_idx < len(row) else ""):
        if not any(_is_name_header_cell(row[i]) for i in range(min(8, len(row)))):
            return None
        name_idx = _find_labor_name_col(row)
    rate_idx, mode = _find_labor_rate_col(row)
    if rate_idx < 0 or not mode:
        return None
    agency_idx = _find_labor_agency_col(row)
    date_cols = [
        (i, _norm_sheet_cell(val))
        for i, val in enumerate(row)
        if _is_labor_date_header(val)
    ]
    return mode, rate_idx, agency_idx, name_idx, date_cols


def _is_cno_worker_label(label: str) -> bool:
    """(CNO…)、(CNO.H GF)…、（CNO.H）… 等劳务姓名行。"""
    s = _norm_sheet_cell(label)
    if not s:
        return False
    if re.search(r"[\(（]\s*CNO[\.\sHh]", s, re.I):
        return True
    if s.upper().startswith("(CNO") or s.startswith("（CNO"):
        return True
    return False


def _is_cno_worker_row_at(row, name_idx: int) -> bool:
    """数据行：按表头确定的姓名列识别 (CNO…（考勤 ID 在 A 列时不看 A 列）。"""
    if name_idx >= 0 and name_idx < len(row) and _is_cno_worker_label(row[name_idx]):
        return True
    for i in range(min(5, len(row))):
        if _is_cno_worker_label(row[i]):
            return True
    return False


def _worker_label_at(row, name_idx: int) -> str:
    if 0 <= name_idx < len(row):
        lab = _norm_sheet_cell(row[name_idx])
        if lab:
            return lab
    for i in range(min(8, len(row))):
        if _is_cno_worker_label(row[i]):
            return _norm_sheet_cell(row[i])
    return _norm_sheet_cell(row[0]) if row else ""


def _should_skip_hourly_worker(worker_label: str, row, job_idx: int) -> bool:
    """仅跳过姓名里带 Sorter 的（计件分拣账号）；Job=SORTER 的工时行仍计入。"""
    if re.search(r"\bSorter\b", worker_label, re.I):
        return True
    return False


def _find_labor_job_col(row) -> int:
    for i, col in enumerate(row):
        if _norm_sheet_cell(col).lower() == "job":
            return i
    return -1


def _row_val(row, key_or_idx, default=None):
    try:
        if isinstance(key_or_idx, int):
            return row[key_or_idx]
        return row[key_or_idx]
    except (KeyError, IndexError, TypeError):
        return default


def _sync_gofo_daily_cost(cur, is_pg: bool, d, d_str: str) -> None:
    """将 Gofo 计件与当日件数写入 daily_cost_summary（与主库同源）。"""
    import pytz

    c = _cols(is_pg)
    t = _tbl(is_pg)
    _ensure_daily_cost_table(cur, is_pg)

    cur.execute(
        _q(
            f"""
            SELECT
                CASE
                    WHEN Operator_Name LIKE 'AAS%' THEN 'AAS'
                    WHEN Operator_Name LIKE 'UNS%' THEN 'A-SHARE'
                    ELSE 'OTHERS'
                END as Agency,
                SUM(Wages) as Piece_Wages,
                COUNT(DISTINCT Operator_Name) as Headcount
            FROM gofo_piece_rate_summary
            WHERE Record_Date = ?
            GROUP BY Agency
            """,
            is_pg,
        ),
        (d_str,),
    )
    for row in cur.fetchall():
        agency = _row_val(row, 'Agency', _row_val(row, 0))
        wages = _row_val(row, 'Piece_Wages', _row_val(row, 1))
        hc = _row_val(row, 'Headcount', _row_val(row, 2))
        _insert_ignore_daily_row(cur, is_pg, d_str, agency)
        cur.execute(
            _q(
                f"""
                UPDATE {t}
                SET {c['piece']} = ?, {c['headcount']} = COALESCE({c['headcount']}, 0) + ?
                WHERE {c['date']} = ? AND {c['agency']} = ?
                """,
                is_pg,
            ),
            (round(wages or 0, 2), hc, d_str, agency),
        )

    cur.execute(
        _q("SELECT SUM(tickets_count), SUM(boxes_count) FROM feishu_raw_data WHERE record_date = ?", is_pg),
        (d_str,),
    )
    f_row = cur.fetchone()
    f_pieces = _row_val(f_row, 0, 0) if f_row else 0
    if f_pieces and f_pieces > 0:
        total_p = int(f_pieces)
        print(f"   - Using Feishu pieces for {d_str}: {total_p}")
    else:
        la_tz = pytz.timezone('America/Los_Angeles')
        next_date = d + timedelta(days=1)
        t_start = la_tz.localize(datetime.combine(d, datetime.min.time().replace(hour=5)))
        t_end = la_tz.localize(datetime.combine(next_date, datetime.min.time().replace(hour=5)))
        cur.execute(
            _q(
                f"""
                SELECT SUM(CASE
                    WHEN vehicle_type = '53英尺' AND vehicle_no = 'G' THEN 0
                    ELSE ((pieces - COALESCE(excluded_pieces, 0)) * {INBOUND_PIECES_ACTUAL_FACTOR})
                END) as total_pieces
                FROM inbound_records
                WHERE created_at >= ? AND created_at < ?
                """,
                is_pg,
            ),
            (t_start.strftime('%Y-%m-%d %H:%M:%S'), t_end.strftime('%Y-%m-%d %H:%M:%S')),
        )
        p_row = cur.fetchone()
        total_p = int(round(float(_row_val(p_row, 'total_pieces', _row_val(p_row, 0, 0)) or 0)))
        print(f"   - Using System pieces for {d_str}: {total_p}")

    _insert_ignore_daily_row(cur, is_pg, d_str, '【当日总计】')
    cur.execute(
        _q(
            f"""
            UPDATE {t}
            SET {c['total_pieces']} = ?, {c['corrected_pieces']} = ?
            WHERE {c['date']} = ? AND {c['agency']} = '【当日总计】'
            """,
            is_pg,
        ),
        (total_p, total_p, d_str),
    )
    cur.execute(
        _q(
            f"""
            UPDATE {t}
            SET {c['total']} = COALESCE({c['hourly']}, 0) + COALESCE({c['piece']}, 0)
            WHERE {c['date']} = ?
            """,
            is_pg,
        ),
        (d_str,),
    )
    cur.execute(
        _q(
            f"""
            SELECT SUM(COALESCE({c['hourly']}, 0)), SUM(COALESCE({c['piece']}, 0)),
                   SUM(COALESCE({c['total']}, 0)), SUM(COALESCE({c['headcount']}, 0))
            FROM {t}
            WHERE {c['date']} = ? AND {c['agency']} != '【当日总计】'
            """,
            is_pg,
        ),
        (d_str,),
    )
    totals = cur.fetchone()
    if totals:
        th = _row_val(totals, 0)
        tp = _row_val(totals, 1)
        tt = _row_val(totals, 2)
        thc = _row_val(totals, 3)
        cur.execute(
            _q(
                f"""
                UPDATE {t}
                SET {c['hourly']} = ?, {c['piece']} = ?, {c['total']} = ?, {c['headcount']} = ?
                WHERE {c['date']} = ? AND {c['agency']} = '【当日总计】'
                """,
                is_pg,
            ),
            (th or 0, tp or 0, tt or 0, thc or 0, d_str),
        )


def _parse_labor_record_date(date_val) -> str:
    """飞书日期列 → YYYY-MM-DD（替代 pandas to_datetime format=mixed）。"""
    s = _norm_sheet_cell(date_val)
    if not s:
        return ""
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})$", s)
    if m:
        mo, da, yr = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if yr < 100:
            yr += 2000
        try:
            return datetime(yr, mo, da).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return ""


def _aggregate_labor_records(all_records: list) -> list:
    """按日期×代理商汇总飞书排班记录，含【当日总计】行。"""
    agency_agg: dict = defaultdict(
        lambda: {"Hourly_Cost": 0.0, "Piece_Cost": 0.0, "Total_Cost": 0.0, "Headcount": 0}
    )
    daily_agg: dict = defaultdict(
        lambda: {"Hourly_Cost": 0.0, "Piece_Cost": 0.0, "Total_Cost": 0.0, "Headcount": 0}
    )

    for rec in all_records:
        hourly = float(rec["Cost"]) if rec.get("Type") == "Hourly" else 0.0
        piece = float(rec["Cost"]) if rec.get("Type") == "Piece" else 0.0
        total = float(rec.get("Cost") or 0.0)
        headcount = int(rec.get("Headcount") or 0)
        rdate = _parse_labor_record_date(rec.get("Date"))
        if not rdate:
            continue
        agency = rec.get("Agency") or ""
        ak = (rdate, agency)
        agency_agg[ak]["Hourly_Cost"] += hourly
        agency_agg[ak]["Piece_Cost"] += piece
        agency_agg[ak]["Total_Cost"] += total
        agency_agg[ak]["Headcount"] += headcount
        daily_agg[rdate]["Hourly_Cost"] += hourly
        daily_agg[rdate]["Piece_Cost"] += piece
        daily_agg[rdate]["Total_Cost"] += total
        daily_agg[rdate]["Headcount"] += headcount

    combined = []
    for (rdate, agency), v in agency_agg.items():
        combined.append({
            "Record_Date": rdate,
            "Agency_Name": agency,
            "Hourly_Cost_USD": round(v["Hourly_Cost"], 2),
            "Piece_Cost_USD": round(v["Piece_Cost"], 2),
            "Total_Cost_USD": round(v["Total_Cost"], 2),
            "Headcount": int(v["Headcount"]),
        })
    for rdate, v in daily_agg.items():
        combined.append({
            "Record_Date": rdate,
            "Agency_Name": "【当日总计】",
            "Hourly_Cost_USD": round(v["Hourly_Cost"], 2),
            "Piece_Cost_USD": round(v["Piece_Cost"], 2),
            "Total_Cost_USD": round(v["Total_Cost"], 2),
            "Headcount": int(v["Headcount"]),
        })

    combined.sort(
        key=lambda x: (
            x["Record_Date"],
            0 if x["Agency_Name"] == "【当日总计】" else 1,
            x["Agency_Name"],
        )
    )
    return combined


def _persist_labor_combined(combined) -> dict:
    """将飞书解析结果写入 daily_cost_summary。"""
    conn, is_pg = _open_labor_db()
    c = _cols(is_pg)
    t = _tbl(is_pg)
    try:
        cur = conn.cursor()
        _ensure_daily_cost_table(cur, is_pg)
        dates_to_refresh = set()
        upsert_count = 0

        for row in combined:
            if hasattr(row, "to_dict"):
                row = row.to_dict()
            rdate = row["Record_Date"]
            agency = row["Agency_Name"]
            if not rdate:
                continue
            dates_to_refresh.add(rdate)
            _insert_ignore_daily_row(cur, is_pg, rdate, agency)
            if agency != '【当日总计】':
                cur.execute(
                    _q(
                        f"""
                        UPDATE {t}
                        SET {c['hourly']} = ?, {c['headcount']} = ?
                        WHERE {c['date']} = ? AND {c['agency']} = ?
                        """,
                        is_pg,
                    ),
                    (row['Hourly_Cost_USD'], row['Headcount'], rdate, agency),
                )
                upsert_count += 1

        print("🔄 正在同步 Gofo 计件数据至汇总表...")
        for rdate_feishu in dates_to_refresh:
            if not rdate_feishu:
                continue
            cur.execute(
                _q(
                    f"""
                    SELECT
                        CASE
                            WHEN Operator_Name LIKE 'AAS%' THEN 'AAS'
                            WHEN Operator_Name LIKE 'UNS%' THEN 'A-SHARE'
                            ELSE 'OTHERS'
                        END as Agency,
                        SUM(Wages) as Piece_Wages
                    FROM gofo_piece_rate_summary
                    WHERE Record_Date = ?
                    GROUP BY Agency
                    """,
                    is_pg,
                ),
                (rdate_feishu,),
            )
            for prow in cur.fetchall():
                agency_mapped = _row_val(prow, 'Agency', _row_val(prow, 0))
                piece_wages = _row_val(prow, 'Piece_Wages', _row_val(prow, 1))
                if agency_mapped == 'OTHERS':
                    continue
                _insert_ignore_daily_row(cur, is_pg, rdate_feishu, agency_mapped)
                cur.execute(
                    _q(
                        f"""
                        UPDATE {t}
                        SET {c['piece']} = ?
                        WHERE {c['date']} = ? AND {c['agency']} = ?
                        """,
                        is_pg,
                    ),
                    (piece_wages, rdate_feishu, agency_mapped),
                )

        print("🧮 正在重新计算总额与当日汇总...")
        for rdate_feishu in dates_to_refresh:
            cur.execute(
                _q(
                    f"""
                    UPDATE {t}
                    SET {c['total']} = COALESCE({c['hourly']}, 0) + COALESCE({c['piece']}, 0)
                    WHERE {c['date']} = ? AND {c['agency']} != '【当日总计】'
                    """,
                    is_pg,
                ),
                (rdate_feishu,),
            )
            if is_pg:
                cur.execute(
                    f"""
                    INSERT INTO {t} ({c['date']}, {c['agency']}, {c['hourly']}, {c['piece']}, {c['total']}, {c['headcount']})
                    SELECT
                        {c['date']},
                        '【当日总计】',
                        SUM(COALESCE({c['hourly']}, 0)),
                        SUM(COALESCE({c['piece']}, 0)),
                        SUM(COALESCE({c['total']}, 0)),
                        SUM(COALESCE({c['headcount']}, 0))
                    FROM {t}
                    WHERE {c['date']} = %s AND {c['agency']} != '【当日总计】'
                    GROUP BY {c['date']}
                    ON CONFLICT ({c['date']}, {c['agency']}) DO UPDATE SET
                        {c['hourly']} = EXCLUDED.{c['hourly']},
                        {c['piece']} = EXCLUDED.{c['piece']},
                        {c['total']} = EXCLUDED.{c['total']},
                        {c['headcount']} = EXCLUDED.{c['headcount']}
                    """,
                    (rdate_feishu,),
                )
            else:
                cur.execute(
                    _q(
                        f"""
                        INSERT OR REPLACE INTO {t}
                            ({c['date']}, {c['agency']}, {c['hourly']}, {c['piece']}, {c['total']}, {c['headcount']})
                        SELECT
                            {c['date']},
                            '【当日总计】',
                            SUM(COALESCE({c['hourly']}, 0)),
                            SUM(COALESCE({c['piece']}, 0)),
                            SUM(COALESCE({c['total']}, 0)),
                            SUM(COALESCE({c['headcount']}, 0))
                        FROM {t}
                        WHERE {c['date']} = ? AND {c['agency']} != '【当日总计】'
                        GROUP BY {c['date']}
                        """,
                        is_pg,
                    ),
                    (rdate_feishu,),
                )

            try:
                la_tz = pytz.timezone('America/Los_Angeles')
                rd = datetime.strptime(rdate_feishu, '%Y-%m-%d').date()
                nd = rd + timedelta(days=1)
                range_start = la_tz.localize(datetime.combine(rd, datetime.min.time().replace(hour=5)))
                range_end = la_tz.localize(datetime.combine(nd, datetime.min.time().replace(hour=5)))
                cur.execute(
                    _q(
                        f"""
                        SELECT SUM(CASE
                            WHEN vehicle_type = '53英尺' AND vehicle_no = 'G' THEN 0
                            ELSE ((pieces - COALESCE(excluded_pieces, 0)) * {INBOUND_PIECES_ACTUAL_FACTOR})
                        END) as total_pieces
                        FROM inbound_records
                        WHERE created_at >= ? AND created_at < ?
                        """,
                        is_pg,
                    ),
                    (
                        range_start.strftime('%Y-%m-%d %H:%M:%S'),
                        range_end.strftime('%Y-%m-%d %H:%M:%S'),
                    ),
                )
                p_r = cur.fetchone()
                tp = int(round(float(_row_val(p_r, 'total_pieces', _row_val(p_r, 0, 0)) or 0)))
                cur.execute(
                    _q(
                        f"""
                        UPDATE {t}
                        SET {c['total_pieces']} = ?, {c['corrected_pieces']} = ?
                        WHERE {c['date']} = ? AND {c['agency']} = '【当日总计】'
                        """,
                        is_pg,
                    ),
                    (tp, tp, rdate_feishu),
                )
            except Exception as e:
                print(f"   ⚠️ Volume Update failed for {rdate_feishu}: {e}")

        conn.commit()
        msg = f"✅ 数据同步与汇总计算完成！已刷新 {len(dates_to_refresh)} 天的完整人工成本。"
        print(msg)
        return {"success": True, "message": msg, "upsert_count": upsert_count}
    except Exception as e:
        conn.rollback()
        msg = f"数据库写入失败: {e}"
        print(f"❌ {msg}")
        return {"success": False, "error": msg}
    finally:
        conn.close()


def run_sync(link=None):
    print("--- 飞书排班数据成本核算 ---")
    
    # --- [FIX] Gofo Sync Refactoring ---
    # Make sync synchronous for the last 3 days to avoid UI race conditions
    today = datetime.now().date()

    import batch_gofo_sync_ultrafast

    for i in range(3):
        d = today - timedelta(days=i)
        d_str = d.strftime("%Y-%m-%d")
        print(f"[Sync] -> Syncing Gofo for {d_str}...")
        try:
            batch_gofo_sync_ultrafast.sync_day_fast(d_str)
            conn, is_pg = _open_labor_db()
            try:
                _sync_gofo_daily_cost(conn.cursor(), is_pg, d, d_str)
                conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"   ⚠️ Sync loop failed for {d_str}: {e}")
    # --- END [FIX] ---

    
    spread_token = SPREADSHEET_TOKEN_DEFAULT
    sheet_id = SHEET_ID_DEFAULT
    
    if link:
        parsed_link = _parse_feishu_sheet_link(link)
        if parsed_link:
            spread_token, sheet_id = parsed_link
        else:
            print("⚠️ 链接解析失败，将使用默认 Token。")

    print("⏳ 正在获取飞书 API Token...")
    try:
        token = get_feishu_tenant_token()
    except Exception as e:
        msg = f"获取飞书 Token 失败，请检查 APP_ID 和 APP_SECRET。错误信息: {e}"
        print(f"❌ {msg}")
        return {"success": False, "error": msg}

    print("⏳ 正在拉取飞书表格数据...")
    try:
        sheet_values = fetch_feishu_sheet_data(token, spread_token, sheet_id)
    except Exception as e:
        msg = f"读取飞书表格失败: {e}"
        print(f"❌ {msg}")
        return {"success": False, "error": msg}

    if not sheet_values:
        msg = "飞书表格为空或读取失败。"
        print(msg)
        return {"success": False, "error": msg}
        
    print(f"✅ 成功拉取数据，共 {len(sheet_values)} 行，开始执行成本核算逻辑...")
    
    # --- DEBUGGING OUTPUT ---
    for i, debug_row in enumerate(sheet_values[:5]):
        print(f"DEBUG ROW {i}: {debug_row}")
    # ------------------------

    all_records = []
    
    current_mode = None
    date_cols = []
    rate_idx = -1
    agency_idx = -1
    name_idx = 0
    job_idx = -1
    workers_parsed = 0
    day_records = 0

    for row in sheet_values:
        if not row:
            continue

        row = [str(item) if item is not None else "" for item in row]

        # 1. 识别表头（可重复出现；支持考勤 ID 列 + Hourly Rate 在 Total Hours/Overtime 之后）
        parsed = _parse_labor_header_row(row)
        if parsed:
            current_mode, rate_idx, agency_idx, name_idx, date_cols = parsed
            job_idx = _find_labor_job_col(row)
            print(
                f"✅ 识别表头: mode={current_mode}, name_col={name_idx}, "
                f"rate_col={rate_idx}, agency_col={agency_idx}, job_col={job_idx}, "
                f"dates={len(date_cols)} -> {[d[1] for d in date_cols[:5]]}..."
            )
            continue

        elif current_mode == 'Hourly' and len(row) > 0 and _is_cno_worker_row_at(row, name_idx):
            rate = _parse_sheet_number(row[rate_idx] if rate_idx < len(row) else "")
            if rate <= 0:
                continue
            agency = row[agency_idx].strip() if agency_idx >= 0 and agency_idx < len(row) else 'Unknown'
            if agency.upper() == 'STOX':
                agency = 'Storx'
            if agency.strip() == '':
                agency = 'Unknown'
            worker_label = _worker_label_at(row, name_idx)
            if _should_skip_hourly_worker(worker_label, row, job_idx):
                continue

            workers_parsed += 1
            for i, date_str in date_cols:
                hours = _parse_sheet_number(row[i] if i < len(row) else "")
                if hours <= 0:
                    continue

                daily_regular = min(hours, 8.0)
                daily_ot = max(hours - 8.0, 0.0)
                daily_cost = (daily_regular * rate) + (daily_ot * rate * 1.5)

                all_records.append({
                    'Date': date_str, 'Agency': agency,
                    'Type': 'Hourly', 'Cost': daily_cost,
                    'Headcount': 1
                })
                day_records += 1
                                
        # 3. 计件成本核算 (Piece Rate) - DEPRECATED in favor of Gofo Sync
        elif False and current_mode == 'Piece' and len(row) > 0 and row[0].strip() == '':
            if len(row) > agency_idx and row[agency_idx].strip() != '':
                if len(row) > rate_idx and row[rate_idx].replace('.', '', 1).isdigit():
                    rate = float(row[rate_idx])
                    agency = row[agency_idx].strip()
                    if agency.upper() == 'STOX': agency = 'Storx'
                    if agency.strip() == '': agency = 'Unknown'
                    
                    for i, date_str in date_cols:
                        if i < len(row):
                            val_str = row[i].strip()
                            if val_str.replace('.', '', 1).isdigit():
                                val = float(val_str)
                                if val > 0:
                                    daily_cost = val * rate
                                    all_records.append({
                                        'Date': date_str, 'Agency': agency, 
                                        'Type': 'Piece', 'Cost': daily_cost,
                                        'Headcount': 0
                                    })

    if not current_mode:
        preview = []
        for i, debug_row in enumerate(sheet_values[:8]):
            cells = [_norm_sheet_cell(c) for c in (debug_row or [])[:12]]
            preview.append(f"行{i + 1}: " + " | ".join(cells) if cells else f"行{i + 1}: (空)")
        hint = "\n".join(preview)
        return {
            "success": False,
            "error": (
                "未能在表格中识别到表头行。需要包含：姓名列（NAME/姓名，可在考勤 ID 列右侧）、"
                "费率列（Hourly Rate/时薪 或 Price/单价）、日期列（如 3/9/26 或 2026-03-09）、"
                "代理商列（Agency/代理商）。请确认飞书链接的 sheet 与工作表一致。"
                f"\n前 8 行预览：\n{hint}"
            ),
        }
    if not date_cols:
        return {
            "success": False,
            "error": "在表头行中未识别到日期列（格式需如 3/9/26 或 2026-03-09），请检查表头是否包含有效日期。",
        }
    if agency_idx == -1:
        return {
            "success": False,
            "error": "未识别到代理商列（Agency/Agence/Company/代理商），请检查表头字段。",
        }

    if not all_records:
        msg = (
            "未从表格中提取到有效排班数据。请确认："
            "1) 姓名列为 (CNO…)/(CNO.H GF)… 格式；"
            "2) 日期列（如 5/4/26）下有工时；"
            "3) Hourly Rate 列有费率。"
            f"（已识别 mode={current_mode}，日期列 {len(date_cols)} 个）"
        )
        print(msg)
        return {"success": False, "error": msg}

    print(f"✅ 解析 {workers_parsed} 名员工、{day_records} 条日工时记录")

    combined = _aggregate_labor_records(all_records)

    debug_match = [
        r for r in combined
        if r.get("Record_Date") == "2026-03-01" and r.get("Agency_Name") == "AAS"
    ]
    if debug_match:
        print(f"DEBUG COMBINED AAS 03-01: {debug_match[0]}")
    
    db_kind = 'PostgreSQL' if USE_POSTGRES else 'SQLite'
    print(f"⏳ 正在将核算结果保存至 {db_kind} -> 表: daily_cost_summary")
    return _persist_labor_combined(combined)

if __name__ == '__main__':
    run_sync()
