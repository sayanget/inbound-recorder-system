import sqlite3
import pandas as pd

conn = sqlite3.connect('d:/project/inbound_python_source/inbound.db')
df = pd.read_sql("SELECT Record_Date, Agency_Name, Hourly_Cost_USD FROM daily_cost_summary WHERE Record_Date='2026-03-01' AND Agency_Name='GF'", conn)
print(df)
conn.close()
