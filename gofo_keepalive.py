import requests
import json
import logging
import time
from datetime import datetime
import os
import sys

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

from gofo_config import get_gofo_token

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# A lightweight endpoint to hit to keep the session active. 
# getInfo is usually a safe, read-only endpoint that requires auth.
URL = "https://dms.gofoexpress.com/prod-api/getInfo"

def ping_gofo():
    TOKEN = get_gofo_token()
    if not TOKEN:
        logging.error("❌ Token not found. Heartbeat skipped.")
        return False

    headers = {
        "Admin-Token": TOKEN,
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "Mozilla/5.0",
    }
    
    try:
        logging.info("Sending heartbeat to Gofo API...")
        res = requests.get(URL, headers=headers, timeout=10)
        
        if res.status_code == 200:
            data = res.json()
            if data.get("code") == 200:
                logging.info(f"✅ Heartbeat successful. User: {data.get('user', {}).get('userName', 'Unknown')}")
                return True
            else:
                logging.error(f"❌ Heartbeat failed, API returned: {data.get('msg')}")
                return False
        elif res.status_code == 401:
            logging.error("❌ Heartbeat failed: 401 Unauthorized. Token has expired.")
            return False
        else:
            logging.error(f"❌ Heartbeat failed: HTTP {res.status_code}")
            return False
            
    except Exception as e:
        logging.error(f"❌ Heartbeat request error: {e}")
        return False

if __name__ == '__main__':
    ping_gofo()
