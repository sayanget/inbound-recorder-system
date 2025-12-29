#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
查找正确的API返回语句
"""

def find_correct_return():
    """查找正确的API返回语句"""
    with open('single_app.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    found_api = False
    for i, line in enumerate(lines):
        if '@app.route(\'/api/stats\')' in line:
            found_api = True
            print(f'API端点在第{i+1}行')
        elif found_api and 'return jsonify({' in line and 'error' not in line:
            print(f'正确的Return语句在第{i+1}行:')
            # 打印接下来的几行
            for j in range(i, min(i+20, len(lines))):
                print(f'{j+1:4d}: {lines[j].rstrip()}')
            break

if __name__ == "__main__":
    find_correct_return()