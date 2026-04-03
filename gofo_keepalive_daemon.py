import time
import logging
import os
import sys

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from gofo_keepalive import ping_gofo

log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gofo_keepalive.log')
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ],
    force=True
)

def run_daemon():
    logging.info("Starting Gofo API Keep-Alive Daemon...")
    while True:
        try:
            success = ping_gofo()
            if not success:
                logging.warning("Ping failed. It might be a temporary network issue or the token actually expired.")
        except Exception as e:
            logging.error(f"Daemon error: {e}")
        
        # Ping every 30 minutes (1800 seconds)
        time.sleep(1800)

if __name__ == "__main__":
    run_daemon()
