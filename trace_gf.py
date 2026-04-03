import sys
sys.path.append('d:/project/inbound_python_source')
from calc_outsource_finance import get_feishu_tenant_token, SPREADSHEET_TOKEN_DEFAULT, fetch_feishu_sheet_data
import pandas as pd
import requests

token = get_feishu_tenant_token()
headers = {"Authorization": f"Bearer {token}"}
meta_url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{SPREADSHEET_TOKEN_DEFAULT}/metainfo"
res = requests.get(meta_url, headers=headers)
sheets = res.json().get('data', {}).get('sheets', [])

all_records = []

for s in sheets:
    sheet_id = s.get('sheetId')
    rows = fetch_feishu_sheet_data(token, SPREADSHEET_TOKEN_DEFAULT, sheet_id)
    if not rows or len(rows) < 2: continue
    
    current_mode = None
    date_cols = []
    rate_idx = -1
    agency_idx = -1
    
    for row in rows:
        if not row: continue
        row = [str(item) if item is not None else "" for item in row]
        if len(row) > 0 and str(row[0]).strip().upper() == 'NAME':
            rate_cols = [c.strip().lower() for c in row if isinstance(c, str)]
            if 'hourly rate' in rate_cols:
                current_mode = 'Hourly'
                rate_idx = rate_cols.index('hourly rate')
                date_cols = [(i, str(val).strip()) for i, val in enumerate(row) if isinstance(val, str) and '/' in val and val != '站点/枢纽']
            for i, col in enumerate(row):
                if isinstance(col, str) and col.strip().lower() in ['agency', 'agence', 'company']:
                    agency_idx = i
                    break
        elif current_mode == 'Hourly' and len(row) > 0 and (row[0].strip().startswith('(CNO') or row[0].strip().startswith('（CNO')):
            if len(row) > rate_idx and row[rate_idx].replace('.', '', 1).isdigit():
                rate = float(row[rate_idx])
                agency = row[agency_idx].strip() if len(row) > agency_idx else 'Unknown'
                if agency.upper() == 'STOX': agency = 'Storx'
                if agency.strip() == '': agency = 'Unknown'
                
                for i, date_str in date_cols:
                    hours = 0.0
                    if i < len(row):
                        val_str = row[i].strip()
                        if val_str.replace('.', '', 1).isdigit():
                            hours = float(val_str)
                    
                    if hours <= 0: continue 
                    daily_regular = min(hours, 8.0)
                    daily_ot = max(hours - 8.0, 0.0)
                    daily_cost = (daily_regular * rate) + (daily_ot * rate * 1.5)
                    
                    all_records.append({
                        'Sheet': s.get('title'),
                        'DateStr': date_str,
                        'Date_Obj': pd.to_datetime(date_str, format='mixed', errors='coerce').strftime('%Y-%m-%d') if pd.notnull(pd.to_datetime(date_str, format='mixed', errors='coerce')) else '',
                        'Name': row[0],
                        'Agency': agency,
                        'Hours': hours,
                        'Rate': rate,
                        'Reg': daily_regular,
                        'OT': daily_ot,
                        'Cost': daily_cost
                    })

df = pd.DataFrame(all_records)
target = df[(df['Date_Obj'] == '2026-03-01') & (df['Agency'] == 'GF')]

with open('d:/project/inbound_python_source/trace_output.txt', 'w', encoding='utf-8') as f:
    for sheet_name, group in target.groupby('Sheet'):
        f.write(f"\n--- From Sheet: {sheet_name} ---\n")
        sum_cost = 0.0
        for _, row in group.iterrows():
            f.write(f"Name: {row['Name']:<35} | DateStr: {row['DateStr']} | Hrs: {row['Hours']:<4} | Rate: {row['Rate']:<4} | Reg: {row['Reg']:<3} | OT: {row['OT']:<3} | Cost: ${row['Cost']:.2f}\n")
            sum_cost += row['Cost']
        f.write(f">> Total for this sheet: ${sum_cost:.2f}\n")
    f.write("\nFinal note: The DB UPSERT processes these sheets sequentially. The last row processed overwrites the earlier ones for 2026-03-01.\n")
