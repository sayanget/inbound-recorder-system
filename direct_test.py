import sys
import os

# 添加项目目录到Python路径
sys.path.append('d:/project/inbound_python_source')

# 导入函数
from single_app import list_data

# 直接调用函数
print("直接调用list_data函数:")
result = list_data()
print("函数返回结果类型:", type(result))
print("函数返回结果:", result)