#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
获取完整页面内容
"""

import requests

def get_full_page():
    """获取完整页面内容"""
    try:
        # 获取页面内容
        response = requests.get('http://localhost:8080/')
        if response.status_code == 200:
            content = response.text
            
            # 保存到文件供检查
            with open('page_content.html', 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"页面内容已保存到 page_content.html，长度: {len(content)} 字符")
            
            # 检查是否包含托盘总数相关的内容
            if '托盘总数' in content:
                print("✓ 页面内容中包含'托盘总数'")
            else:
                print("✗ 页面内容中不包含'托盘总数'")
                
            # 查找托盘总数相关的HTML元素
            if 'id="totalPallets"' in content:
                print("✓ 页面内容中包含id='totalPallets'元素")
            else:
                print("✗ 页面内容中不包含id='totalPallets'元素")
                
            # 查找total_pallets翻译
            if 'total_pallets: "托盘总数"' in content:
                print("✓ 页面内容中包含total_pallets翻译")
            else:
                print("✗ 页面内容中不包含total_pallets翻译")
                
            # 查找统计摘要部分
            if '数据概览' in content:
                print("✓ 页面内容中包含'数据概览'")
            else:
                print("✗ 页面内容中不包含'数据概览'")
                
        else:
            print(f"获取页面失败，状态码: {response.status_code}")
    except Exception as e:
        print(f"获取页面内容时出错: {e}")

if __name__ == "__main__":
    get_full_page()