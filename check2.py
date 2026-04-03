import sqlite3
import pandas as pd

conn = sqlite3.connect('d:/project/inbound_python_source/inbound.db')
df = pd.read_sql("SELECT * FROM daily_cost_summary", conn)

print('Export Sum of Agencies:', df[df.Agency_Name != '【当日总计】'].Hourly_Cost_USD.sum())
print('Export Sum of [当日总计]:', df[df.Agency_Name == '【当日总计】'].Hourly_Cost_USD.sum())

# Date matching check
print("\nDate comparison:")
print("Min date:", df.Record_Date.min())
print("Max date:", df.Record_Date.max())

conn.close()
