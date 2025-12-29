import requests
import json

# 测试/api/list接口
try:
    response = requests.get('http://localhost:8080/api/list', timeout=10)
    if response.status_code == 200:
        records = response.json()
        print(f"Total records: {len(records)}")
        
        # 查找53英尺且包含G的记录
        g_53ft_records = [r for r in records if r.get("vehicle_type") == "53英尺" and "G" in str(r.get("vehicle_no", ""))]
        print(f"53英尺且包含G的记录数量: {len(g_53ft_records)}")
        
        # 显示这些记录的详细信息
        for r in g_53ft_records:
            print(f"  ID: {r['id']}, Vehicle: {r['vehicle_type']}, Plate: '{r['vehicle_no']}', Created: {r['created_at']}")
            
        # 显示最近的几条记录
        print("\n最近的5条记录:")
        for i, r in enumerate(records[:5]):
            print(f"  {i+1}. ID: {r['id']}, Vehicle: {r['vehicle_type']}, Plate: '{r['vehicle_no']}', Created: {r['created_at']}")
    else:
        print(f"Error: {response.status_code} - {response.text}")
except Exception as e:
    print(f"Request failed: {e}")