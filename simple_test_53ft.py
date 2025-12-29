# 简单测试53英尺车辆处理逻辑

# 模拟API中的处理逻辑
def process_53ft_vehicle(data):
    vt = data.get("vehicle_type", "")
    if vt == "53英尺":
        data["unit"] = "托盘"
        # 当车辆类型为53英尺时，默认是24托盘，如有输入装载量，按照输入的托盘计算货量
        load_amount = data.get("load_amount")
        if load_amount is not None and load_amount != "":
            # 如果提供了装载量，使用提供的装载量计算件数
            try:
                load_amount = int(load_amount)
                data["load_amount"] = load_amount
                data["pieces"] = load_amount * 344
            except (ValueError, TypeError):
                # 如果装载量不是有效数字，使用默认值
                data["load_amount"] = 24
                data["pieces"] = 24 * 344
        else:
            # 如果没有提供装载量，使用默认值
            data["load_amount"] = 24
            data["pieces"] = 24 * 344
    
    # 确保load_amount和pieces字段存在
    if "load_amount" not in data:
        data["load_amount"] = 0
    if "pieces" not in data:
        data["pieces"] = 0
        
    return data

# 测试数据1：不提供load_amount
data1 = {
    "vehicle_type": "53英尺",
    "dock_no": 1
}

print("测试数据1 - 不提供load_amount:")
result1 = process_53ft_vehicle(data1)
print("处理结果:", result1)
print("load_amount:", result1.get("load_amount"))
print("pieces:", result1.get("pieces"))

# 测试数据2：提供load_amount
data2 = {
    "vehicle_type": "53英尺",
    "dock_no": 2,
    "load_amount": 10
}

print("\n测试数据2 - 提供load_amount:")
result2 = process_53ft_vehicle(data2)
print("处理结果:", result2)
print("load_amount:", result2.get("load_amount"))
print("pieces:", result2.get("pieces"))

# 测试数据3：load_amount为空字符串
data3 = {
    "vehicle_type": "53英尺",
    "dock_no": 3,
    "load_amount": ""
}

print("\n测试数据3 - load_amount为空字符串:")
result3 = process_53ft_vehicle(data3)
print("处理结果:", result3)
print("load_amount:", result3.get("load_amount"))
print("pieces:", result3.get("pieces"))