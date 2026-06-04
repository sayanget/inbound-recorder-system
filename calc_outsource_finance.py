import os
import requests
import pandas as pd
import sqlite3
import re
import pytz
from datetime import datetime, timedelta

# --- 飞书 API 配置 ---
FEISHU_APP_ID = os.getenv('FEISHU_APP_ID', 'cli_a9fc1c1c0bb8dbcb')
FEISHU_APP_SECRET = os.getenv('FEISHU_APP_SECRET', 'XeStEZgDlQQUnUU93w1d3emYSdMSfiq6')
SPREADSHEET_TOKEN_DEFAULT = 'FYWYsrb70ho1xEtq9unceocwnSf'
SHEET_ID_DEFAULT = 'V2dsq4'

# 与 single_app 一致：入库实到件数 = (录入 − excluded_pieces) × 系数；53+G 为 0
INBOUND_PIECES_ACTUAL_FACTOR = float(os.environ.get("INBOUND_PIECES_ACTUAL_FACTOR", "0.76"))

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

def run_sync(link=None):
    print("--- 飞书排班数据成本核算 ---")
    
    # --- [FIX] Gofo Sync Refactoring ---
    # Make sync synchronous for the last 3 days to avoid UI race conditions
    today = datetime.now().date()
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'inbound.db')
    
    import batch_gofo_sync_ultrafast
    import sqlite3
    import pytz
    
    for i in range(3):
        d = today - timedelta(days=i)
        d_str = d.strftime("%Y-%m-%d")
        print(f"[Sync] -> Syncing Gofo for {d_str}...")
        try:
            batch_gofo_sync_ultrafast.sync_day_fast(d_str)
            
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            
            # 1. Update Piece Cost AND Headcount from gofo_piece_rate_summary
            cur.execute("""
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
            """, (d_str,))
            piece_data = cur.fetchall()
            
            for row in piece_data:
                agency = row['Agency']
                wages = row['Piece_Wages']
                hc = row['Headcount']
                
                # Ensure row exists
                cur.execute("INSERT OR IGNORE INTO daily_cost_summary (Record_Date, Agency_Name) VALUES (?, ?)", (d_str, agency))
                # Update piece wages and headcount
                cur.execute("""
                    UPDATE daily_cost_summary 
                    SET Piece_Cost_USD = ?, Headcount = COALESCE(Headcount, 0) + ? 
                    WHERE Record_Date = ? AND Agency_Name = ?
                """, (round(wages or 0, 2), hc, d_str, agency))
            
            # 2. Update Volume Stats for the day (05:00 boundary)
            # [REFINEMENT] Prioritize feishu_raw_data for pieces if available (e.g. manual entries for Sundays)
            cur.execute("SELECT SUM(tickets_count), SUM(boxes_count) FROM feishu_raw_data WHERE record_date = ?", (d_str,))
            f_row = cur.fetchone()
            f_pieces = f_row[0] if f_row and f_row[0] else 0
            
            if f_pieces > 0:
                total_p = int(f_pieces)
                print(f"   - Using Feishu pieces for {d_str}: {total_p}")
            else:
                la_tz = pytz.timezone('America/Los_Angeles')
                request_date = d
                next_date = request_date + timedelta(days=1)
                req_5am_la = la_tz.localize(datetime.combine(request_date, datetime.min.time().replace(hour=5)))
                next_5am_la = la_tz.localize(datetime.combine(next_date, datetime.min.time().replace(hour=5)))
                t_start = req_5am_la.astimezone(la_tz)
                t_end = next_5am_la.astimezone(la_tz)
                
                cur.execute(f"""
                    SELECT SUM(CASE 
                        WHEN vehicle_type = '53英尺' AND vehicle_no = 'G' THEN 0 
                        ELSE ((pieces - COALESCE(excluded_pieces, 0)) * {INBOUND_PIECES_ACTUAL_FACTOR})
                    END) as total_pieces 
                FROM inbound_records 
                WHERE created_at >= ? AND created_at < ?
                """, (t_start.strftime('%Y-%m-%d %H:%M:%S'), t_end.strftime('%Y-%m-%d %H:%M:%S')))
                p_row = cur.fetchone()
                total_p = int(round(float(p_row[0]))) if p_row and p_row[0] is not None else 0
                print(f"   - Using System pieces for {d_str}: {total_p}")
                
            corrected_p = total_p
            
            cur.execute("INSERT OR IGNORE INTO daily_cost_summary (Record_Date, Agency_Name) VALUES (?, ?)", (d_str, '【当日总计】'))
            cur.execute("""
                UPDATE daily_cost_summary 
                SET Total_Pieces = ?, Corrected_Pieces = ? 
                WHERE Record_Date = ? AND Agency_Name = '【当日总计】'
            """, (total_p, corrected_p, d_str))
            
            # 3. Update Total Costs using COALESCE to prevent NULL values
            cur.execute("""
                UPDATE daily_cost_summary 
                SET Total_Cost_USD = COALESCE(Hourly_Cost_USD, 0) + COALESCE(Piece_Cost_USD, 0) 
                WHERE Record_Date = ?
            """, (d_str,))
            
            # 4. Recalculate Grand Totals
            cur.execute("""
                SELECT SUM(COALESCE(Hourly_Cost_USD, 0)), SUM(COALESCE(Piece_Cost_USD, 0)), 
                       SUM(COALESCE(Total_Cost_USD, 0)), SUM(COALESCE(Headcount, 0))
                FROM daily_cost_summary 
                WHERE Record_Date = ? AND Agency_Name != '【当日总计】'
            """, (d_str,))
            totals = cur.fetchone()
            if totals:
                th, tp, tt, thc = totals
                cur.execute("""
                    UPDATE daily_cost_summary 
                    SET Hourly_Cost_USD = ?, Piece_Cost_USD = ?, Total_Cost_USD = ?, Headcount = ?
                    WHERE Record_Date = ? AND Agency_Name = '【当日总计】'
                """, (th or 0, tp or 0, tt or 0, thc or 0, d_str))
            
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"   ⚠️ Sync loop failed for {d_str}: {e}")
    # --- END [FIX] ---

    
    spread_token = SPREADSHEET_TOKEN_DEFAULT
    sheet_id = SHEET_ID_DEFAULT
    
    if link:
        match = re.search(r'sheets/([a-zA-Z0-9]+)\?sheet=([a-zA-Z0-9]+)', link)
        if match:
            spread_token = match.group(1)
            sheet_id = match.group(2)
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
        
    df = pd.DataFrame(all_records)
    
    # 拆分展示
    df['Hourly_Cost'] = df.apply(lambda r: r['Cost'] if r['Type'] == 'Hourly' else 0.0, axis=1)
    df['Piece_Cost'] = df.apply(lambda r: r['Cost'] if r['Type'] == 'Piece' else 0.0, axis=1)
    df['Total_Cost'] = df['Cost']
    # Use format=mixed to handle mixed date formats correctly without warnings if dates are valid
    df['Date_Obj'] = pd.to_datetime(df['Date'], format='mixed', errors='coerce')
    
    # 按公司汇总
    summary = df.groupby(['Date_Obj', 'Date', 'Agency']).agg(
        Hourly_Cost=('Hourly_Cost', 'sum'),
        Piece_Cost=('Piece_Cost', 'sum'),
        Total_Cost=('Total_Cost', 'sum'),
        Headcount=('Headcount', 'sum')
    ).reset_index()
    
    # 计算当日总计
    daily_total = df.groupby(['Date_Obj', 'Date']).agg(
        Hourly_Cost=('Hourly_Cost', 'sum'),
        Piece_Cost=('Piece_Cost', 'sum'),
        Total_Cost=('Total_Cost', 'sum'),
        Headcount=('Headcount', 'sum')
    ).reset_index()
    daily_total['Agency'] = '【当日总计】'
    
    # 合并、排序与清理格式
    combined = pd.concat([summary, daily_total], ignore_index=True)
    combined['Is_Total'] = combined['Agency'] == '【当日总计】'
    combined['Date_Obj'] = combined['Date_Obj'].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notnull(x) else '')
    combined = combined.sort_values(['Date_Obj', 'Is_Total', 'Agency']).drop(columns=['Date', 'Is_Total'])
    
    for col in ['Hourly_Cost', 'Piece_Cost', 'Total_Cost']:
        combined[col] = combined[col].round(2)
    combined['Headcount'] = combined['Headcount'].astype(int)
        
    combined.rename(columns={
        'Date_Obj': 'Record_Date', 
        'Agency': 'Agency_Name',
        'Headcount': 'Headcount',
        'Hourly_Cost': 'Hourly_Cost_USD',
        'Piece_Cost': 'Piece_Cost_USD',
        'Total_Cost': 'Total_Cost_USD'
    }, inplace=True)
    
    # Debug combined for 03-01 AAS
    debug_match = combined[(combined['Record_Date'] == '3/1/26') & (combined['Agency_Name'] == 'AAS')]
    if not debug_match.empty:
        print(f"DEBUG COMBINED AAS 03-01: {debug_match.iloc[0].to_dict()}")
    
    # --- 4. 本地 SQLite 数据库归档 ---
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'inbound.db')
    table_name = 'daily_cost_summary'
    
    print(f"⏳ 正在将核算结果保存至本地数据库: {db_path} -> 表: {table_name}")
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        
        # Create table if not exists (preserves all historical data)
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                Record_Date        TEXT NOT NULL,
                Agency_Name        TEXT NOT NULL,
                Hourly_Cost_USD    REAL DEFAULT 0,
                Piece_Cost_USD     REAL DEFAULT 0,
                Total_Cost_USD     REAL DEFAULT 0,
                Headcount          INTEGER DEFAULT 0,
                PRIMARY KEY (Record_Date, Agency_Name)
            )
        """)
        
        # Non-destructive upsert: update only hourly cost and headcount
        upsert_count = 0
        dates_to_refresh = set()
        
        for _, row in combined.iterrows():
            rdate = row['Record_Date']
            agency = row['Agency_Name']
            dates_to_refresh.add(rdate)
            
            # 1. Ensure the row exists
            cur.execute(f"INSERT OR IGNORE INTO {table_name} (Record_Date, Agency_Name) VALUES (?, ?)", (rdate, agency))
            
            # 2. Update Hourly Part (only for non-total rows, total is handled at the end)
            if agency != '【当日总计】':
                cur.execute(f"""
                    UPDATE {table_name}
                    SET Hourly_Cost_USD = ?, Headcount = ?
                    WHERE Record_Date = ? AND Agency_Name = ?
                """, (row['Hourly_Cost_USD'], row['Headcount'], rdate, agency))
                upsert_count += 1

        # --- 5. Sync Piece-Rate Data from Gofo into Summary ---
        print("🔄 正在同步 Gofo 计件数据至汇总表...")
        for rdate_feishu in dates_to_refresh:
            # Note: rdate_feishu is already in YYYY-MM-DD
            rdate_gofo = rdate_feishu
            if not rdate_gofo:
                continue
                
            # Aggregate from gofo_piece_rate_summary
            # Mapping logic: AAS Sorters -> AAS, UNS Sorters -> UNS
            cur.execute("""
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
            """, (rdate_gofo,))
            
            piece_data = cur.fetchall()
            for agency_mapped, piece_wages in piece_data:
                if agency_mapped == 'OTHERS': continue
                
                # Ensure row exists for this agency (e.g. UNS might not be in Feishu)
                cur.execute(f"INSERT OR IGNORE INTO {table_name} (Record_Date, Agency_Name) VALUES (?, ?)", (rdate_feishu, agency_mapped))
                
                # Update Piece Cost
                cur.execute(f"""
                    UPDATE {table_name}
                    SET Piece_Cost_USD = ?
                    WHERE Record_Date = ? AND Agency_Name = ?
                """, (piece_wages, rdate_feishu, agency_mapped))

        # --- 6. Recalculate Total_Cost_USD and 【当日总计】 ---
        print("🧮 正在重新计算总额与当日汇总...")
        for rdate_feishu in dates_to_refresh:
            # Update individual totals: Total = Hourly + Piece
            cur.execute(f"""
                UPDATE {table_name}
                SET Total_Cost_USD = COALESCE(Hourly_Cost_USD, 0) + COALESCE(Piece_Cost_USD, 0)
                WHERE Record_Date = ? AND Agency_Name != '【当日总计】'
            """, (rdate_feishu,))
            
            # Recalculate 【当日总计】 (Cost parts)
            cur.execute(f"""
                INSERT OR REPLACE INTO {table_name} (Record_Date, Agency_Name, Hourly_Cost_USD, Piece_Cost_USD, Total_Cost_USD, Headcount)
                SELECT 
                    Record_Date, 
                    '【当日总计】',
                    SUM(COALESCE(Hourly_Cost_USD, 0)),
                    SUM(COALESCE(Piece_Cost_USD, 0)),
                    SUM(COALESCE(Total_Cost_USD, 0)),
                    SUM(COALESCE(Headcount, 0))
                FROM {table_name}
                WHERE Record_Date = ? AND Agency_Name != '【当日总计】'
                GROUP BY Record_Date
            """, (rdate_feishu,))

            # Update Volume Stats on the total row
            try:
                la_tz = pytz.timezone('America/Los_Angeles')
                # rdate_feishu is in YYYY-MM-DD
                rd = datetime.strptime(rdate_feishu, '%Y-%m-%d').date()
                nd = rd + timedelta(days=1)
                range_start = la_tz.localize(datetime.combine(rd, datetime.min.time().replace(hour=5))).astimezone(la_tz)
                range_end = la_tz.localize(datetime.combine(nd, datetime.min.time().replace(hour=5))).astimezone(la_tz)
                
                cur.execute(f"""
                    SELECT SUM(CASE 
                        WHEN vehicle_type = '53英尺' AND vehicle_no = 'G' THEN 0 
                        ELSE ((pieces - COALESCE(excluded_pieces, 0)) * {INBOUND_PIECES_ACTUAL_FACTOR})
                    END) as total_pieces 
                    FROM inbound_records 
                    WHERE created_at >= ? AND created_at < ?
                """, (range_start.strftime('%Y-%m-%d %H:%M:%S'), 
                      range_end.strftime('%Y-%m-%d %H:%M:%S')))
                p_r = cur.fetchone()
                tp = int(round(float(p_r[0]))) if p_r and p_r[0] is not None else 0
                cp = tp
                
                cur.execute(f"UPDATE {table_name} SET Total_Pieces = ?, Corrected_Pieces = ? WHERE Record_Date = ? AND Agency_Name = '【当日总计】'", (tp, cp, rdate_feishu))
            except Exception as e:
                print(f"   ⚠️ Volume Update failed for {rdate_feishu}: {e}")

        conn.commit()
        conn.close()
        msg = f"✅ 数据同步与汇总计算完成！已刷新 {len(dates_to_refresh)} 天的完整人工成本。"
        print(msg)
        return {"success": True, "message": msg}
    except Exception as e:
        msg = f"数据库写入失败: {e}"
        print(f"❌ {msg}")
        return {"success": False, "error": msg}

if __name__ == '__main__':
    run_sync()
