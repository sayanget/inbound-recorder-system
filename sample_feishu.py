import requests
import json

def sample_feishu():
    app_id = 'cli_a9fc1c1c0bb8dbcb'
    app_secret = 'XeStEZgDlQQUnUU93w1d3emYSdMSfiq6'
    spreadsheet_token = 'SvBYstNvyhvh8ptbq29cMc7Ln8c'
    sheet_id = '24dfdb'
    
    # Get Token
    r_tok = requests.post('https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal/', 
                         json={'app_id': app_id, 'app_secret': app_secret})
    token = r_tok.json().get('tenant_access_token')
    headers = {'Authorization': f'Bearer {token}'}
    
    # Sample different ranges
    ranges = ["A1:C5", "A100000:C100005", "A112000:C112005"]
    
    for r in ranges:
        print(f"\nSampling range {r}...")
        url = f"https://open.feishu.cn/open-apis/sheets/v2/spreadsheets/{spreadsheet_token}/values/{sheet_id}!{r}?valueRenderOption=FormattedValue"
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            vals = res.json().get("data", {}).get("valueRange", {}).get("values", [])
            print(f"  Rows found: {len(vals)}")
            for row in vals:
                print(f"  {row}")
        else:
            print(f"  Error: {res.text}")

if __name__ == "__main__":
    sample_feishu()
