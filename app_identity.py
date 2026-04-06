"""应用指纹、版权与版本标识。勿将密钥写入本文件；用环境变量注入。"""
import os

# 版权与制作人（核心标识）
COPYRIGHT_HOLDER = "Fan Yang"
COPYRIGHT_YEAR = "2026"
COPYRIGHT_NOTICE = (
    f"Copyright (c) {COPYRIGHT_YEAR} {COPYRIGHT_HOLDER}. "
    "All rights reserved. Unauthorized reproduction, distribution, or commercial exploitation is prohibited."
)
# 商业使用声明：部署与 API 对外可见；措辞侧重可主张之权利，避免难以证成的绝对化事实承诺
COMMERCIAL_USE_NOTICE = (
    "本软件及相关文档、界面、衍生成果之著作权及其他知识产权，除法律另有规定外，均归 Fan Yang 享有。"
    "任何以营利为目的或面向公众/客户的部署、托管、再许可、销售、集成、提供商业服务或其他商业利用，均须事先取得 Fan Yang 书面许可。"
    "未经许可的前述行为构成侵权；Fan Yang 保留在适用法律框架内采取一切救济措施之权利，包括但不限于：要求停止侵害、消除影响、证据保全与调查取证、提起民事、行政或刑事程序（如适用），并主张损害赔偿、合理维权开支及可依法支持之其他救济。"
)

# 你的标识：部署时设置 APP_FINGERPRINT=你的代号/组织名
APP_FINGERPRINT = os.environ.get("APP_FINGERPRINT", "inbound-recorder")

_GIT = (
    os.environ.get("GIT_COMMIT")
    or os.environ.get("SOURCE_VERSION")
    or os.environ.get("GIT_REV")
    or ""
)
GIT_COMMIT_SHORT = (_GIT[:12] if _GIT else None)


def identity_dict():
    return {
        "fingerprint": APP_FINGERPRINT,
        "git": GIT_COMMIT_SHORT,
        "author": COPYRIGHT_HOLDER,
        "copyright": COPYRIGHT_NOTICE,
        "commercial_use": COMMERCIAL_USE_NOTICE,
    }
