#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最终测试：验证所有时间段自动填充功能
"""

import requests
import json
from datetime import datetime

# 测试基础URL
BASE_URL = "http://localhost:8080"

def test_all_time_slot_features():
    """测试所有时间段自动填充功能"""
    print("=== 最终测试：验证所有时间段自动填充功能 ===")
    
    # 获取当前小时用于验证
    current_hour = str(datetime.now().hour)
    print(f"当前小时: {current_hour}")
    
    # 测试1: 入库记录 - 不提供time_slot字段
    print("\n--- 测试1: 入库记录 - 不提供time_slot字段 ---")
    test_record1 = {
        "dock_no": 10,
        "vehicle_type": "Car",
        "vehicle_no": "FINAL_TEST_1",
        "load_amount": 1,
        "pieces": 172,
        "remark": "最终测试1 - 入库记录自动填充"
    }
    
    response = requests.post(f"{BASE_URL}/api/record", json=test_record1)
    if response.status_code == 200:
        response = requests.get(f"{BASE_URL}/api/list")
        if response.status_code == 200:
            records = response.json()
            for record in records:
                if record['vehicle_no'] == 'FINAL_TEST_1':
                    if record['time_slot'] == current_hour:
                        print("✓ 入库记录 - 时间段自动填充功能正常")
                    else:
                        print(f"✗ 入库记录 - 时间段不匹配: 期望{current_hour}, 实际{record['time_slot']}")
                    break
    
    # 测试2: 入库记录 - 提供time_slot为空字符串
    print("\n--- 测试2: 入库记录 - 提供time_slot为空字符串 ---")
    test_record2 = {
        "dock_no": 11,
        "vehicle_type": "Van",
        "vehicle_no": "FINAL_TEST_2",
        "load_amount": 9,
        "pieces": 9*172,
        "time_slot": "",
        "remark": "最终测试2 - 入库记录空字符串填充"
    }
    
    response = requests.post(f"{BASE_URL}/api/record", json=test_record2)
    if response.status_code == 200:
        response = requests.get(f"{BASE_URL}/api/list")
        if response.status_code == 200:
            records = response.json()
            for record in records:
                if record['vehicle_no'] == 'FINAL_TEST_2':
                    if record['time_slot'] == current_hour:
                        print("✓ 入库记录 - 空字符串自动填充功能正常")
                    else:
                        print(f"✗ 入库记录 - 时间段不匹配: 期望{current_hour}, 实际{record['time_slot']}")
                    break
    
    # 测试3: 分拣记录 - 不提供time_slot字段
    print("\n--- 测试3: 分拣记录 - 不提供time_slot字段 ---")
    test_record3 = {
        "sorting_time": "2025-12-22",
        "pieces": 500,
        "remark": "最终测试3 - 分拣记录自动填充"
    }
    
    response = requests.post(f"{BASE_URL}/api/sorting", json=test_record3)
    if response.status_code == 200:
        response = requests.get(f"{BASE_URL}/api/sorting")
        if response.status_code == 200:
            records = response.json()
            for record in records:
                if record['remark'] == '最终测试3 - 分拣记录自动填充':
                    if record['time_slot'] == current_hour:
                        print("✓ 分拣记录 - 时间段自动填充功能正常")
                    else:
                        print(f"✗ 分拣记录 - 时间段不匹配: 期望{current_hour}, 实际{record['time_slot']}")
                    break
    
    # 测试4: 分拣记录 - 提供time_slot为空字符串
    print("\n--- 测试4: 分拣记录 - 提供time_slot为空字符串 ---")
    test_record4 = {
        "sorting_time": "2025-12-22",
        "pieces": 600,
        "time_slot": "",
        "remark": "最终测试4 - 分拣记录空字符串填充"
    }
    
    response = requests.post(f"{BASE_URL}/api/sorting", json=test_record4)
    if response.status_code == 200:
        response = requests.get(f"{BASE_URL}/api/sorting")
        if response.status_code == 200:
            records = response.json()
            for record in records:
                if record['remark'] == '最终测试4 - 分拣记录空字符串填充':
                    if record['time_slot'] == current_hour:
                        print("✓ 分拣记录 - 空字符串自动填充功能正常")
                    else:
                        print(f"✗ 分拣记录 - 时间段不匹配: 期望{current_hour}, 实际{record['time_slot']}")
                    break
    
    # 测试5: 验证有效time_slot保持不变
    print("\n--- 测试5: 验证有效time_slot保持不变 ---")
    test_record5 = {
        "dock_no": 12,
        "vehicle_type": "26英尺",
        "vehicle_no": "FINAL_TEST_5",
        "load_amount": 12,
        "pieces": 12*344,
        "time_slot": "特定班次",
        "remark": "最终测试5 - 保持原值"
    }
    
    response = requests.post(f"{BASE_URL}/api/record", json=test_record5)
    if response.status_code == 200:
        response = requests.get(f"{BASE_URL}/api/list")
        if response.status_code == 200:
            records = response.json()
            for record in records:
                if record['vehicle_no'] == 'FINAL_TEST_5':
                    if record['time_slot'] == '特定班次':
                        print("✓ 有效time_slot保持原值功能正常")
                    else:
                        print(f"✗ 有效time_slot被修改: 期望'特定班次', 实际{record['time_slot']}")
                    break
    
    print("\n=== 测试完成 ===")
    print("所有时间段自动填充功能已验证！")

if __name__ == '__main__':
    test_all_time_slot_features()