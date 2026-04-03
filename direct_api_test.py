#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接测试API函数
"""

import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入Flask应用
from single_app import app, get_statistics
import json

def test_api_function():
    """直接测试API函数"""
    with app.test_request_context('/api/stats'):
        try:
            # 直接调用函数
            result = get_statistics()
            print("API函数返回结果:")
            print(result)
            print("JSON数据:")
            print(json.dumps(result.get_json(), indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"测试API函数时出错: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_api_function()