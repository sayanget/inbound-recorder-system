import requests
import json
from datetime import datetime

# 获取今天的日期
today = datetime.now().strftime('%Y-%m-%d')
print(f"Testing all APIs for today ({today})...")

# 测试/api/list接口
print("\n1. Testing /api/list:")
try:
    response = requests.get('http://localhost:8080/api/list', timeout=10)
    if response.status_code == 200:
        records = response.json()
        g_53ft_records = [r for r in records if r.get("vehicle_type") == "53英尺" and "G" in str(r.get("vehicle_no", ""))]
        print(f"  Total records: {len(records)}")
        print(f"  53英尺包含G的记录数量: {len(g_53ft_records)}")
    else:
        print(f"  Error: {response.status_code}")
except Exception as e:
    print(f"  Request failed: {e}")

# 测试/api/history接口
print("\n2. Testing /api/history:")
try:
    response = requests.get(f'http://localhost:8080/api/history?date={today}', timeout=10)
    if response.status_code == 200:
        data = response.json()
        records = data.get('records', [])
        stats = data.get('stats', {})
        g_53ft_records = [r for r in records if r.get("vehicle_type") == "53英尺" and "G" in str(r.get("vehicle_no", ""))]
        print(f"  Total records returned: {len(records)}")
        print(f"  53英尺包含G的记录数量: {len(g_53ft_records)}")
        print(f"  Total vehicles in stats: {stats.get('total_vehicles')}")
        print(f"  Vehicle stats: {stats.get('vehicle_stats')}")
    else:
        print(f"  Error: {response.status_code}")
except Exception as e:
    print(f"  Request failed: {e}")

# 测试/api/stats接口
print("\n3. Testing /api/stats:")
try:
    response = requests.get('http://localhost:8080/api/stats', timeout=10)
    if response.status_code == 200:
        data = response.json()
        print(f"  Total vehicles: {data.get('total_vehicles')}")
        print(f"  Total pieces: {data.get('total_pieces')}")
        print(f"  Total pallets: {data.get('total_pallets')}")
        print(f"  Vehicle stats: {data.get('vehicle_stats')}")
    else:
        print(f"  Error: {response.status_code}")
except Exception as e:
    print(f"  Request failed: {e}")

# 测试/api/export_csv接口
print("\n4. Testing /api/export_csv:")
try:
    response = requests.get(f'http://localhost:8080/api/export_csv?date={today}', timeout=10)
    if response.status_code == 200:
        print(f"  CSV export successful, size: {len(response.content)} bytes")
    else:
        print(f"  Error: {response.status_code}")
except Exception as e:
    print(f"  Request failed: {e}")

print("\nAll tests completed!")