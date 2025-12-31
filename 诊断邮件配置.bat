@echo off
chcp 65001 > nul
echo ============================================================
echo 邮件发送故障排查工具
echo ============================================================
echo.

python -c "
import smtplib
import sys

print('正在测试SMTP连接...')
print()

# 读取配置
try:
    from email_config import SMTP_SERVER, SMTP_PORT, SENDER_EMAIL, SENDER_PASSWORD
    print(f'SMTP服务器: {SMTP_SERVER}')
    print(f'SMTP端口: {SMTP_PORT}')
    print(f'发件人邮箱: {SENDER_EMAIL}')
    print(f'密码长度: {len(SENDER_PASSWORD)} 字符')
    print()
except ImportError:
    print('错误: 未找到email_config.py文件')
    sys.exit(1)

# 测试连接
try:
    print('步骤1: 连接SMTP服务器...')
    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10)
    print('✅ 连接成功')
    
    print('步骤2: 启动TLS加密...')
    server.starttls()
    print('✅ TLS启动成功')
    
    print('步骤3: 登录邮箱...')
    server.login(SENDER_EMAIL, SENDER_PASSWORD)
    print('✅ 登录成功')
    
    server.quit()
    print()
    print('='*60)
    print('✅ 所有测试通过！邮件配置正确')
    print('='*60)
    
except smtplib.SMTPAuthenticationError as e:
    print(f'❌ 登录失败: {e}')
    print()
    print('可能的原因:')
    print('1. 邮箱密码错误')
    print('2. 未使用应用专用密码（Gmail需要）')
    print('3. 未开启"允许不够安全的应用"（部分邮箱）')
    print()
    print('解决方法:')
    if 'gmail' in SMTP_SERVER.lower():
        print('Gmail用户请:')
        print('1. 开启两步验证')
        print('2. 生成应用专用密码')
        print('3. 使用应用专用密码替换SENDER_PASSWORD')
    
except smtplib.SMTPServerDisconnected as e:
    print(f'❌ 连接断开: {e}')
    print()
    print('可能的原因:')
    print('1. SMTP服务器地址或端口错误')
    print('2. 网络连接问题')
    print('3. 防火墙阻止连接')
    print('4. 邮箱服务商限制')
    
except Exception as e:
    print(f'❌ 未知错误: {e}')
    import traceback
    traceback.print_exc()

print()
"

pause
