import requests
import json

# 测试53英尺车辆功能
url = "http://localhost:8080/api/record"

# 测试数据1：不输入装载量，应该使用默认24托盘
data1 = {
    "vehicle_type": "53英尺",
    "dock_no": 1
}

print("测试1：不输入装载量，应该使用默认24托盘")
print("输入数据:", data1)

response1 = requests.post(url, headers={"Content-Type": "application/json"}, data=json.dumps(data1))
print("响应:", response1.json())

# 等待一段时间确保数据写入数据库
import time
time.sleep(1)

# 查询刚插入的记录
list_url = "http://localhost:8080/api/list"
list_response = requests.get(list_url)
if list_response.status_code == 200:
    records = list_response.json()
    # 查找我们刚刚插入的记录
    for record in records:
        if record.get("dock_no") == 1 and record.get("vehicle_type") == "53英尺":
            print("数据库中的记录:")
            print(f"  装载量: {record.get('load_amount')}")
            print(f"  件数: {record.get('pieces')}")
            break
else:
    print("无法获取记录列表")