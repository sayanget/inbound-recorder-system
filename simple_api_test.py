#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单API测试
"""

import requests
import json

def simple_api_test():
    """简单API测试"""
    try:
        # 直接访问API
        response = requests.get('http://localhost:8080/api/stats')
        print(f"状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            print("解析后的JSON数据:")
            print(json.dumps(data, indent=2, ensure_ascii=False))
            
            # 检查字段
            print("\n字段检查:")
            for key in data.keys():
                print(f"  {key}: {data[key]}")
    except Exception as e:
        print(f"测试出错: {e}")

if __name__ == "__main__":
    simple_api_test()