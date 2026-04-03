"""
邮件配置向导
帮助用户快速配置邮箱信息
"""

import os

def get_smtp_config(email_provider):
    """根据邮箱类型返回SMTP配置"""
    configs = {
        '1': {
            'name': 'Gmail',
            'smtp_server': 'smtp.gmail.com',
            'smtp_port': 587,
            'help': '''
Gmail配置说明：
1. 开启两步验证：Google账户 -> 安全性 -> 两步验证
2. 生成应用专用密码：安全性 -> 应用专用密码
3. 选择"邮件"和"Windows计算机"
4. 将生成的16位密码填入下方
'''
        },
        '2': {
            'name': 'Yahoo',
            'smtp_server': 'smtp.mail.yahoo.com',
            'smtp_port': 587,
            'help': '''
Yahoo配置说明：
1. 登录Yahoo账户
2. 进入账户安全设置
3. 生成应用专用密码
4. 将密码填入下方
'''
        },
        '3': {
            'name': 'QQ邮箱',
            'smtp_server': 'smtp.qq.com',
            'smtp_port': 587,
            'help': '''
QQ邮箱配置说明：
1. 登录QQ邮箱
2. 设置 -> 账户 -> POP3/SMTP服务
3. 开启SMTP服务
4. 获取授权码（不是QQ密码）
5. 将授权码填入下方
'''
        },
        '4': {
            'name': '163邮箱',
            'smtp_server': 'smtp.163.com',
            'smtp_port': 465,
            'help': '''
163邮箱配置说明：
1. 登录163邮箱
2. 设置 -> POP3/SMTP/IMAP
3. 开启SMTP服务
4. 获取授权码
5. 将授权码填入下方
'''
        },
        '5': {
            'name': 'Outlook/Hotmail',
            'smtp_server': 'smtp-mail.outlook.com',
            'smtp_port': 587,
            'help': '''
Outlook配置说明：
1. 使用Outlook账户密码
2. 或生成应用专用密码
'''
        }
    }
    return configs.get(email_provider)

def main():
    print("=" * 60)
    print("           邮件配置向导")
    print("=" * 60)
    print()
    
    # 选择邮箱类型
    print("请选择您的发件邮箱类型：")
    print("1. Gmail")
    print("2. Yahoo")
    print("3. QQ邮箱")
    print("4. 163邮箱")
    print("5. Outlook/Hotmail")
    print("6. 其他（手动配置）")
    print()
    
    choice = input("请输入选项 (1-6): ").strip()
    
    if choice == '6':
        # 手动配置
        print("\n手动配置模式")
        smtp_server = input("SMTP服务器地址: ").strip()
        smtp_port = input("SMTP端口 (通常是587或465): ").strip()
        sender_email = input("发件人邮箱: ").strip()
        sender_password = input("邮箱密码/授权码: ").strip()
    else:
        config = get_smtp_config(choice)
        if not config:
            print("无效的选项！")
            return
        
        print(f"\n您选择了: {config['name']}")
        print(config['help'])
        print()
        
        smtp_server = config['smtp_server']
        smtp_port = config['smtp_port']
        
        sender_email = input(f"请输入您的{config['name']}邮箱地址: ").strip()
        sender_password = input(f"请输入密码/授权码: ").strip()
    
    # 收件人邮箱（默认值）
    print()
    recipient_email = input("收件人邮箱 [默认: sayanget@yahoo.com]: ").strip()
    if not recipient_email:
        recipient_email = "sayanget@yahoo.com"
    
    # 发送时间
    print()
    report_time = input("每天发送时间 (24小时制, 如 08:00) [默认: 08:00]: ").strip()
    if not report_time:
        report_time = "08:00"
    
    # 生成配置文件
    config_content = f'''# 每日邮件报告配置文件
# 由配置向导自动生成

# ==================== 邮件服务器配置 ====================

# SMTP服务器地址
SMTP_SERVER = "{smtp_server}"

# SMTP端口
SMTP_PORT = {smtp_port}

# 发件人邮箱
SENDER_EMAIL = "{sender_email}"

# 发件人邮箱密码或应用专用密码
SENDER_PASSWORD = "{sender_password}"

# 收件人邮箱
RECIPIENT_EMAIL = "{recipient_email}"

# ==================== 报告发送时间配置 ====================

# 每天发送报告的时间 (24小时制, 格式: "HH:MM")
REPORT_TIME = "{report_time}"

# ==================== 其他配置 ====================

# 是否在发送后删除临时Excel文件
DELETE_TEMP_FILE = False

# 邮件主题前缀
EMAIL_SUBJECT_PREFIX = "入库系统每日数据汇总"
'''
    
    # 保存配置文件
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'email_config.py')
    
    # 检查是否已存在配置文件
    if os.path.exists(config_path):
        overwrite = input(f"\n配置文件已存在，是否覆盖? (Y/N): ").strip().upper()
        if overwrite != 'Y':
            print("已取消配置")
            return
    
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(config_content)
    
    print()
    print("=" * 60)
    print("配置完成！")
    print("=" * 60)
    print()
    print("配置信息：")
    print(f"  SMTP服务器: {smtp_server}:{smtp_port}")
    print(f"  发件人: {sender_email}")
    print(f"  收件人: {recipient_email}")
    print(f"  发送时间: 每天 {report_time}")
    print()
    print("配置文件已保存到: email_config.py")
    print()
    print("下一步：")
    print("1. 运行 '测试邮件发送.bat' 测试邮件功能")
    print("2. 运行 '启动邮件服务.bat' 启动定时任务")
    print()
    
    # 询问是否立即测试
    test_now = input("是否立即发送测试邮件? (Y/N): ").strip().upper()
    if test_now == 'Y':
        print("\n正在发送测试邮件...")
        try:
            from daily_email_report import send_daily_report
            send_daily_report()
            print("\n测试邮件发送完成！请检查收件箱。")
        except Exception as e:
            print(f"\n测试邮件发送失败: {str(e)}")
            print("请检查配置是否正确")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n配置已取消")
    except Exception as e:
        print(f"\n配置过程出错: {str(e)}")
    
    input("\n按回车键退出...")
