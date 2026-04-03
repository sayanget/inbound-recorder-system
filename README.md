# 入库记录系统 (Inbound Recorder System)

一个基于 Flask 的入库记录管理系统，用于记录和管理仓库入库、分拣和托盘数据。

## 功能特点

### 核心功能
- 📦 **入库记录管理** - 记录车辆入库信息，包括道口号、车辆类型、车牌号、装载量等
- 📊 **分拣记录管理** - 记录每日分拣数据
- 🎯 **托盘统计** - 统计托盘数据
- 📈 **数据统计与可视化** - 实时统计和图表展示
- 📅 **历史记录查询** - 按日期范围查询历史数据
- 📤 **数据导出** - 导出Excel格式报表

### 高级功能
- 👥 **用户权限管理** - 多用户登录，权限分级（管理员/普通用户）
- 🌐 **离线数据支持** - 支持离线录入，自动同步
- 📧 **每日邮件报告** - 自动生成并发送每日数据汇总邮件
- 🕐 **时区支持** - 自动处理洛杉矶时区（America/Los_Angeles）
- 📱 **响应式设计** - 支持桌面和移动设备

## 技术栈

- **后端**: Python 3.x + Flask
- **数据库**: SQLite
- **前端**: HTML5 + CSS3 + JavaScript
- **图表**: Chart.js
- **Excel生成**: openpyxl
- **邮件发送**: smtplib
- **定时任务**: schedule

## 快速开始

### 1. 安装依赖

```bash
# 运行安装脚本
安装依赖.bat

# 或手动安装
pip install -r requirements.txt
```

### 2. 配置邮件服务（可选）

```bash
# 运行配置向导
配置邮箱.bat

# 或手动编辑 email_config.py
```

### 3. 启动应用

```bash
# 方式1：使用一键启动脚本
一键启动.bat

# 方式2：手动启动
python single_app.py
```

应用将在 `http://localhost:5000` 启动

### 4. 启动邮件服务（可选）

```bash
启动邮件服务.bat
```

## 项目结构

```
inbound_python_source/
├── single_app.py           # 主应用程序
├── daily_email_report.py   # 邮件报告脚本
├── email_config.py         # 邮件配置（需自行创建）
├── setup_email_config.py   # 邮件配置向导
├── requirements.txt        # Python依赖
├── inbound.db             # SQLite数据库
├── static/                # 静态资源
│   ├── css/              # 样式文件
│   ├── js/               # JavaScript文件
│   ├── login.html        # 登录页面
│   ├── index.html        # 主页面
│   ├── sorting.html      # 分拣页面
│   ├── pallet.html       # 托盘页面
│   └── admin.html        # 管理页面
├── 一键启动.bat           # 快速启动脚本
├── 启动邮件服务.bat       # 邮件服务启动脚本
├── 配置邮箱.bat           # 邮件配置脚本
└── 备份项目.bat           # 项目备份脚本
```

## 数据库结构

### users 表
- id: 用户ID
- username: 用户名
- password: 密码（加密存储）
- role: 角色（admin/user）
- created_at: 创建时间

### inbound_records 表
- id: 记录ID
- dock_no: 道口号
- vehicle_type: 车辆类型
- vehicle_no: 车牌号
- unit: 单位
- load_amount: 装载量
- pieces: 件数
- time_slot: 时间段
- shift_type: 班次
- remark: 备注
- created_by: 创建人
- created_at: 创建时间

### sorting_records 表
- id: 记录ID
- sorting_time: 分拣日期
- pieces: 件数
- time_slot: 时间段
- remark: 备注
- created_at: 创建时间

### pallet_records 表
- id: 记录ID
- pallet_time: 托盘日期
- pieces: 件数
- time_slot: 时间段
- remark: 备注
- created_at: 创建时间

## 默认用户

- **管理员账户**: 
  - 用户名: `admin`
  - 密码: `admin123`

- **普通用户**: 
  - 用户名: `user`
  - 密码: `user123`

⚠️ **首次使用后请立即修改默认密码！**

## 邮件报告功能

系统支持每日自动发送数据汇总邮件，包含：
- 入库总件数和车辆数
- 分拣总件数和记录数
- 车辆类型统计
- 详细数据Excel附件

配置步骤：
1. 运行 `配置邮箱.bat` 或手动创建 `email_config.py`
2. 填写SMTP服务器信息和邮箱凭据
3. 设置报告发送时间
4. 运行 `启动邮件服务.bat` 启动定时任务

## 部署

### 本地部署
参见"快速开始"部分

### Docker部署
```bash
docker-compose up -d
```

### 云平台部署
详见 `DEPLOYMENT.md` 和 `DEPLOYMENT_FULL.md`

## 离线功能

系统支持离线数据录入：
1. 离线时，数据会保存在浏览器本地存储
2. 恢复网络后，自动同步到服务器
3. 支持手动触发同步

## 数据导出

支持导出以下格式的报表：
- Excel (.xlsx) - 包含完整数据和格式
- 按日期范围筛选
- 自动计算统计数据

## 备份与恢复

```bash
# 备份项目
备份项目.bat

# 备份会创建包含所有核心文件的压缩包
```

## 开发说明

### 添加新功能
1. 在 `single_app.py` 中添加路由
2. 在 `static/` 中添加前端页面
3. 更新数据库结构（如需要）

### 调试模式
在 `single_app.py` 中设置：
```python
app.run(debug=True, host='0.0.0.0', port=5000)
```

## 常见问题

### 1. 数据库锁定错误
- 确保只有一个应用实例在运行
- 检查数据库文件权限

### 2. 邮件发送失败
- 检查SMTP服务器配置
- 确认使用应用专用密码（如Gmail）
- 检查网络连接

### 3. 时区问题
- 系统默认使用洛杉矶时区
- 可在代码中修改 `LA_TZ` 变量

## 许可证

本项目仅供内部使用。

## 更新日志

### v1.0.0 (2025-12-28)
- ✨ 初始版本发布
- 📦 入库、分拣、托盘记录功能
- 👥 用户权限管理
- 📧 每日邮件报告
- 🌐 离线数据支持
- 📊 数据统计与可视化

## 联系方式

如有问题或建议，请联系系统管理员。
