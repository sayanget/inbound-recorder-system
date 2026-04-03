import sys
import os
from datetime import datetime, timedelta

# Ensure we can import the sync script
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from calc_gofo_piece_rate import fetch_and_summarize_gofo_piece_rate

def run_batch():
    start_date = datetime(2026, 2, 10)
    end_date = datetime(2026, 3, 9)
    
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        print(f"\n>>> Processing Gofo Sync for: {date_str}")
        try:
            result = fetch_and_summarize_gofo_piece_rate(date_str)
            print(f"Result: {result}")
        except Exception as e:
            print(f"Error processing {date_str}: {e}")
        
        current_date += timedelta(days=1)
    
    print("\nBatch Gofo Sync Complete!")

if __name__ == "__main__":
    run_batch()
