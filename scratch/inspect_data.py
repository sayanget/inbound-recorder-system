import sqlite3

conn = sqlite3.connect('inbound.db')
cursor = conn.cursor()

print("--- feishu_raw_data sample ---")
cursor.execute("SELECT record_date, destination, SUM(tickets_count), SUM(boxes_count) FROM feishu_raw_data GROUP BY record_date, destination ORDER BY record_date DESC LIMIT 5")
print(cursor.fetchall())

print("--- gofo_center_collect_stats sample ---")
cursor.execute("SELECT record_date, destin_name, SUM(waybill_cnt), SUM(package_cnt) FROM gofo_center_collect_stats GROUP BY record_date, destin_name ORDER BY record_date DESC LIMIT 5")
print(cursor.fetchall())

print("--- outbound_records sample ---")
cursor.execute("SELECT record_date, route_code, SUM(vehicle_count), SUM(cost) FROM outbound_records GROUP BY record_date, route_code ORDER BY record_date DESC LIMIT 5")
print(cursor.fetchall())

print("--- gofo_tms_shuttle_completed sample ---")
cursor.execute("SELECT record_date, destination, SUM(waybill_total) FROM gofo_tms_shuttle_completed GROUP BY record_date, destination ORDER BY record_date DESC LIMIT 5")
print(cursor.fetchall())

conn.close()
