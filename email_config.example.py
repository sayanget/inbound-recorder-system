# 邮件配置示例文件
# 请复制此文件为 email_config.py 并填写您的实际配置

# ==================== 邮件服务器配置 ====================

# SMTP服务器地址
# Gmail: smtp.gmail.com
# Yahoo: smtp.mail.yahoo.com
# Outlook: smtp-mail.outlook.com
SMTP_SERVER = "smtp.gmail.com"

# SMTP端口
SMTP_PORT = 587

# 发件人邮箱
SENDER_EMAIL = "your_email@gmail.com"

# 发件人邮箱密码或应用专用密码
# 注意：Gmail需要使用应用专用密码，不是账户密码
SENDER_PASSWORD = "your_app_password_here"

# 收件人邮箱
RECIPIENT_EMAIL = "recipient@example.com"

# ==================== 报告发送时间配置 ====================

# 每天发送报告的时间 (24小时制, 格式: "HH:MM")
REPORT_TIME = "08:00"

# ==================== 其他配置 ====================

# 是否在发送后删除临时Excel文件
DELETE_TEMP_FILE = False

# 邮件主题前缀
EMAIL_SUBJECT_PREFIX = "入库系统每日数据汇总"

# ==================== 数据库备份配置 ====================

# 数据库备份发送时间 (24小时制, 格式: "HH:MM")
BACKUP_TIME = "02:00"

# 是否在发送后删除本地备份压缩文件
DELETE_BACKUP_FILE = False

# 数据库备份邮件主题前缀
BACKUP_EMAIL_SUBJECT_PREFIX = "数据库备份"

# 邮件附件最大大小限制 (MB)
# 如果备份文件超过此大小，将发送不带附件的通知邮件
MAX_ATTACHMENT_SIZE_MB = 25
