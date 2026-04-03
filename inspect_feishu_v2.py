import requests
import json

def inspect():
    app_id = 'cli_a9fc1c1c0bb8dbcb'
    app_secret = 'XeStEZgDlQQUnUU93w1d3emYSdMSfiq6'
    spreadsheet_token = 'SvBYstNvyhvh8ptbq29cMc7Ln8c'
    
    # Get Token
    r_tok = requests.post('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/', 
                         json={'app_id': app_id, 'app_secret': app_secret})
    token = r_tok.json().get('tenant_access_token')
    headers = {'Authorization': f'Bearer {token}'}
    
    # Get Meta
    url_meta = f'https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/metainfo'
    res_meta = requests.get(url_meta, headers=headers)
    
    if res_meta.status_code == 200:
        sheets = res_meta.json().get('data', {}).get('sheets', [])
        print(f"Found {len(sheets)} sheets:")
        for s in sheets:
            print(f"- {s.get('title')} (ID: {s.get('sheetId')})")
            
        # Also try to read some values from the first sheet if 24dfdb is empty
        for s in sheets:
            target_id = s.get('sheetId')
            url_values = f'https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values/{target_id}!A1:E5'
            res_values = requests.get(url_values, headers=headers)
            if res_values.status_code == 200:
                vals = res_values.json().get('data', {}).get('valueRange', {}).get('values', [])
                print(f"\nSheet {s.get('title')} ({target_id}): found {len(vals)} rows")
                if vals:
                    print(f"  Header or first row: {vals[0]}")
            else:
                print(f"\nError reading {target_id}: {res_values.text}")
    else:
        print(f"Error reading meta: {res_meta.status_code} {res_meta.text}")

if __name__ == "__main__":
    inspect()
