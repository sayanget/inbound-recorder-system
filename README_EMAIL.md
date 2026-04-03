# 每日数据汇总邮件发送功能使用说明

## 功能介绍

该功能可以每天自动汇总入库系统的数据，并通过邮件发送到指定邮箱。

### 主要功能：
1. **自动数据汇总**：每天自动汇总前一天的入库记录和分拣记录
2. **生成Excel报表**：包含详细的入库记录、分拣记录和统计汇总
3. **邮件发送**：自动发送带附件的HTML格式邮件
4. **定时任务**：可配置每天固定时间自动发送

### 报表内容：
- 入库总件数、车辆数统计
- 分拣总件数、记录数统计
- 按车辆类型分类统计
- 详细的入库记录列表
- 详细的分拣记录列表

---

## 安装步骤

### 1. 安装依赖包

首先需要安装必要的Python包。打开命令行，进入项目目录，运行：

```bash
pip install schedule
```

注意：其他依赖包（sqlite3, smtplib, openpyxl, pytz等）应该已经在项目中安装。

### 2. 配置邮箱信息

编辑 `email_config.py` 文件，填写您的邮箱配置：

```python
# 发件人邮箱（用于发送邮件）
SENDER_EMAIL = "your_email@gmail.com"

# 发件人邮箱密码或应用专用密码
SENDER_PASSWORD = "your_app_password_here"

# 收件人邮箱（已设置为 sayanget@yahoo.com）
RECIPIENT_EMAIL = "sayanget@yahoo.com"

# 每天发送报告的时间（24小时制）
REPORT_TIME = "08:00"
```

---

## 邮箱配置指南

### Gmail 配置

1. **开启两步验证**
   - 登录 Google 账户
   - 进入"安全性"设置
   - 开启"两步验证"

2. **生成应用专用密码**
   - 在"安全性"页面找到"应用专用密码"
   - 选择"邮件"和"Windows计算机"
   - 生成16位密码
   - 将这个密码填入 `SENDER_PASSWORD`

3. **配置示例**
   ```python
   SMTP_SERVER = "smtp.gmail.com"
   SMTP_PORT = 587
   SENDER_EMAIL = "your_email@gmail.com"
   SENDER_PASSWORD = "abcd efgh ijkl mnop"  # 16位应用专用密码
   ```

### Yahoo 邮箱配置

1. **生成应用专用密码**
   - 登录 Yahoo 账户
   - 进入账户安全设置
   - 生成应用专用密码

2. **配置示例**
   ```python
   SMTP_SERVER = "smtp.mail.yahoo.com"
   SMTP_PORT = 587
   SENDER_EMAIL = "your_email@yahoo.com"
   SENDER_PASSWORD = "your_app_password"
   ```

### QQ 邮箱配置

1. **开启SMTP服务**
   - 登录QQ邮箱
   - 进入"设置" -> "账户"
   - 开启"POP3/SMTP服务"
   - 获取授权码

2. **配置示例**
   ```python
   SMTP_SERVER = "smtp.qq.com"
   SMTP_PORT = 587
   SENDER_EMAIL = "your_email@qq.com"
   SENDER_PASSWORD = "your_authorization_code"  # 授权码，不是QQ密码
   ```

### 163 邮箱配置

1. **开启SMTP服务**
   - 登录163邮箱
   - 进入"设置" -> "POP3/SMTP/IMAP"
   - 开启"SMTP服务"
   - 获取授权码

2. **配置示例**
   ```python
   SMTP_SERVER = "smtp.163.com"
   SMTP_PORT = 465  # 或 25
   SENDER_EMAIL = "your_email@163.com"
   SENDER_PASSWORD = "your_authorization_code"
   ```

---

## 使用方法

### 方法一：立即测试发送

如果想立即测试发送一封邮件（发送昨天的数据），编辑 `daily_email_report.py` 文件，找到最后几行：

```python
if __name__ == "__main__":
    # 如果需要立即测试发送，取消下面这行的注释
    send_daily_report()  # 取消这行的注释
    
    # 启动定时任务
    # schedule_daily_report()  # 注释掉这行
```

然后运行：
```bash
python daily_email_report.py
```

### 方法二：启动定时任务

如果想让程序每天自动发送，保持默认配置：

```python
if __name__ == "__main__":
    # 如果需要立即测试发送，取消下面这行的注释
    # send_daily_report()
    
    # 启动定时任务
    schedule_daily_report()
```

然后运行：
```bash
python daily_email_report.py
```

程序会持续运行，每天在配置的时间（默认08:00）自动发送邮件。

### 方法三：后台运行（Windows）

创建一个批处理文件 `start_email_service.bat`：

```batch
@echo off
echo 启动每日邮件报告服务...
python daily_email_report.py
pause
```

双击运行该批处理文件，程序会在后台持续运行。

### 方法四：使用Windows任务计划程序

1. 打开"任务计划程序"
2. 创建基本任务
3. 设置触发器为"每天"
4. 设置操作为"启动程序"
5. 程序选择 Python 解释器路径
6. 参数填写：`daily_email_report.py`
7. 起始于：项目目录路径

---

## 邮件内容示例

### 邮件主题
```
入库系统每日数据汇总 - 2025年12月25日
```

### 邮件正文
包含：
- 📊 总体统计（入库总件数、车辆数、分拣总件数等）
- 🚚 车辆类型统计表格
- 详细数据Excel附件

### Excel附件
包含三个工作表：
1. **入库记录**：所有入库记录的详细信息
2. **分拣记录**：所有分拣记录的详细信息
3. **统计汇总**：各项统计数据

---

## 常见问题

### Q1: 邮件发送失败怎么办？

**A:** 检查以下几点：
1. 确认邮箱配置正确（邮箱地址、密码/授权码）
2. 确认SMTP服务器和端口正确
3. 确认已开启邮箱的SMTP服务
4. 检查网络连接是否正常
5. 查看控制台输出的错误信息

### Q2: 如何修改发送时间？

**A:** 编辑 `email_config.py` 文件，修改 `REPORT_TIME` 的值：
```python
REPORT_TIME = "09:30"  # 改为早上9:30发送
```

### Q3: 如何发送多个收件人？

**A:** 修改 `daily_email_report.py` 中的 `send_email` 函数，将收件人改为列表：
```python
msg['To'] = ', '.join(['email1@example.com', 'email2@example.com'])
```

### Q4: 如何修改报表的日期范围？

**A:** 默认发送前一天的数据。如果需要修改，可以在 `send_daily_report()` 函数中修改：
```python
# 获取数据汇总（指定日期）
target_date = datetime(2025, 12, 25).date()
summary_data = get_daily_summary(target_date)
```

### Q5: 程序关闭后定时任务会停止吗？

**A:** 是的。定时任务需要程序持续运行。建议：
- 使用Windows任务计划程序
- 或者让程序在服务器上持续运行
- 或者使用系统服务方式运行

### Q6: 如何查看发送历史？

**A:** 程序会在控制台输出发送日志。建议将输出重定向到日志文件：
```bash
python daily_email_report.py >> email_log.txt 2>&1
```

---

## 高级配置

### 自定义邮件模板

编辑 `daily_email_report.py` 中的 `generate_email_body()` 函数，可以自定义HTML邮件模板。

### 添加更多统计项

在 `calculate_statistics()` 函数中添加更多统计逻辑，然后在邮件模板中显示。

### 修改Excel样式

在 `create_excel_report()` 函数中修改 openpyxl 的样式设置。

---

## 技术支持

如有问题，请检查：
1. Python版本（建议3.7+）
2. 依赖包是否正确安装
3. 数据库文件是否存在
4. 邮箱配置是否正确

---

## 文件说明

- `daily_email_report.py` - 主程序文件
- `email_config.py` - 邮箱配置文件
- `README_EMAIL.md` - 本说明文档
- `inbound.db` - 数据库文件（自动生成）
- `daily_report_YYYYMMDD.xlsx` - 生成的Excel报表（自动生成）

---

## 更新日志

### v1.0 (2025-12-26)
- 初始版本
- 支持每日自动汇总数据
- 支持生成Excel报表
- 支持邮件发送
- 支持定时任务
