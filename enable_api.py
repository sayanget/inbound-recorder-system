import requests
from google.oauth2 import service_account
from google.auth.transport.requests import Request
import json

KEY_PATH = r"D:\sysoft\my-ai-billing-07d8ff61850f.json"
PROJECT_ID = "my-ai-billing"

def get_access_token():
    credentials = service_account.Credentials.from_service_account_file(
        KEY_PATH, scopes=['https://www.googleapis.com/auth/cloud-platform']
    )
    credentials.refresh(Request())
    return credentials.token

def enable_api():
    token = get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Try enabling cloudquotas.googleapis.com
    url = f"https://serviceusage.googleapis.com/v1/projects/{PROJECT_ID}/services/cloudquotas.googleapis.com:enable"
    resp = requests.post(url, headers=headers)
    print("Enable API response:", resp.status_code, resp.text)
    
if __name__ == "__main__":
    enable_api()
