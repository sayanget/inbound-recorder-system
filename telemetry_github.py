"""
强关联上报（可选）：洛杉矶时间 + OS 稳定机器标识 + 主机名 + 访问端 IP/UA + 校验指纹。
须 TELEMETRY_GITHUB_ENABLE=1；Token 仅存部署环境。Issue 评论可能含可识别信息，请使用私有仓库并自担合规责任。

白名单（命中则不上报）：TELEMETRY_WHITELIST_*（见 _is_whitelisted）。

加固（仍非密码学意义上的防篡改）：
- 部署在 Render 等反向代理后：设置 TRUST_PROXY_HEADERS=1，使 X-Forwarded-For 参与真实 IP。
- 双通道：TELEMETRY_BACKUP_URL + TELEMETRY_BACKUP_SECRET，HMAC-SHA256 签名 JSON，自建接收端验签后写入只追加存储。
- GitHub Issue 可被删评论/删库；重要记录应依赖自建 Webhook + 数据库/对象存储。
- 泄露副本上的采集可被伪造、阻断、改白名单；更强约束需许可证服务器、按客户构建水印等。
"""
from __future__ import annotations

import fnmatch
import getpass
import hashlib
import hmac
import json
import os
import platform
import re
import secrets
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_ROOT = os.path.dirname(os.path.abspath(__file__))
_STATE_PATH = os.path.join(_ROOT, ".telemetry_github_state.json")


def _ensure_dotenv() -> None:
    """与 single_app 启动目录无关，从项目根加载 .env（与 telemetry_github.py 同目录）。"""
    try:
        from dotenv import load_dotenv

        load_dotenv(os.path.join(_ROOT, ".env"))
    except ImportError:
        pass


def normalize_github_repo(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    lower = s.lower()
    if "github.com/" in lower:
        idx = lower.rfind("github.com/")
        s = s[idx + len("github.com/") :]
    s = s.strip().strip("/")
    parts = [p for p in s.split("/") if p]
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return s


def _env_on(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


def _format_time_los_angeles() -> str:
    """America/Los_Angeles，ISO 8601 含本地偏移（PST/PDT）。"""
    try:
        from zoneinfo import ZoneInfo

        z = ZoneInfo("America/Los_Angeles")
    except Exception:
        try:
            import pytz

            z = pytz.timezone("America/Los_Angeles")
        except Exception:
            return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + " (UTC)"
    dt = datetime.now(z).replace(microsecond=0)
    return dt.isoformat()


def _post_signed_backup(payload: Dict[str, Any]) -> bool:
    """
    可选第二通道：POST JSON，含 HMAC-SHA256(sig)。
    验签：hex = HMAC_SHA256(secret, canonical_json + '|' + ts + '|' + nonce)，utf-8。
    """
    url = os.environ.get("TELEMETRY_BACKUP_URL", "").strip()
    secret = (os.environ.get("TELEMETRY_BACKUP_SECRET") or "").strip()
    if not url or not secret:
        return False
    ts = str(int(time.time()))
    nonce = secrets.token_hex(16)
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    sig = hmac.new(
        secret.encode("utf-8"),
        f"{canonical}|{ts}|{nonce}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    out: Dict[str, Any] = {
        "payload": payload,
        "ts": ts,
        "nonce": nonce,
        "sig": sig,
    }
    import requests

    try:
        r = requests.post(
            url,
            json=out,
            timeout=22,
            headers={"Content-Type": "application/json"},
        )
        if r.status_code in (200, 201, 202, 204):
            print("[telemetry_github] 备用 Webhook 已接受。", flush=True)
            return True
        print(
            f"[telemetry_github] 备用 Webhook HTTP {r.status_code} {r.text[:300]}",
            flush=True,
        )
    except Exception as e:
        print(f"[telemetry_github] 备用 Webhook: {e}", flush=True)
    return False


def _csv_items(name: str) -> list[str]:
    return [x.strip() for x in (os.environ.get(name) or "").split(",") if x.strip()]


def _is_whitelisted(
    fp: str, sid: str, client_ip: str, hostname: str
) -> bool:
    """
    白名单命中则不上报。支持：
    TELEMETRY_WHITELIST_FINGERPRINTS — 关联指纹 SHA256（整段 64 位十六进制，逗号分隔）
    TELEMETRY_WHITELIST_MACHINE_IDS — 稳定机器 ID（逗号分隔，大小写不敏感）
    TELEMETRY_WHITELIST_IPS — 客户端 IP，支持 fnmatch（如 127.0.0.1,192.168.*.*,10.*.*.*）
    TELEMETRY_WHITELIST_HOSTNAMES — 主机名，支持 * 通配
    """
    fp_l = fp.lower()
    for x in _csv_items("TELEMETRY_WHITELIST_FINGERPRINTS"):
        if x.lower() == fp_l:
            return True
    sid_l = sid.lower()
    for x in _csv_items("TELEMETRY_WHITELIST_MACHINE_IDS"):
        if x.lower() == sid_l:
            return True
    if client_ip:
        for pat in _csv_items("TELEMETRY_WHITELIST_IPS"):
            if fnmatch.fnmatch(client_ip, pat) or client_ip == pat:
                return True
    if hostname:
        hn = hostname.lower()
        for pat in _csv_items("TELEMETRY_WHITELIST_HOSTNAMES"):
            if fnmatch.fnmatch(hn, pat.lower()) or hn == pat.lower():
                return True
    return False


def _log_skip(msg: str) -> None:
    print(f"[telemetry_github] {msg}", flush=True)


def stable_machine_id() -> str:
    """
    跨平台、重装前一般不变的机器级标识（优先于纯哈希，便于与系统/运维记录对齐）。
    """
    sys = platform.system()
    if sys == "Windows":
        try:
            import winreg

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography"
            ) as k:
                return str(winreg.QueryValueEx(k, "MachineGuid")[0])
        except Exception:
            pass
    if sys == "Linux":
        for p in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    s = f.read().strip()
                    if s:
                        return s
            except OSError:
                pass
    if sys == "Darwin":
        try:
            out = subprocess.run(
                ["ioreg", "-rd1", "-c", "IOPlatformExpert"],
                capture_output=True,
                text=True,
                timeout=8,
            )
            m = re.search(
                r'"IOPlatformUUID"\s*=\s*"([^"]+)"', out.stdout or "", re.I
            )
            if m:
                return m.group(1)
        except Exception:
            pass
    return ""


def association_fingerprint() -> str:
    """与 stable_machine_id + 主机名绑定的 SHA256（全 64 位），用于交叉校验。"""
    salt = os.environ.get("TELEMETRY_SALT", "inbound-telemetry-v1")
    sid = stable_machine_id()
    raw = "|".join(
        [
            sid,
            platform.node() or "",
            str(uuid.getnode()),
            platform.machine() or "",
            platform.system() or "",
            salt,
        ]
    ).encode("utf-8", errors="replace")
    return hashlib.sha256(raw).hexdigest()


def process_os_user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return ""


def client_ip_from_request(request: Any) -> str:
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    xri = request.headers.get("X-Real-IP", "")
    if xri:
        return xri.strip()
    try:
        return request.remote_addr or ""
    except Exception:
        return ""


def _load_state() -> Dict[str, Any]:
    try:
        with open(_STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state: Dict[str, Any]) -> None:
    try:
        with open(_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except OSError:
        pass


def _build_body(
    time_la: str,
    stable_id: str,
    hostname: str,
    fp: str,
    client_ip: str,
    user_agent: str,
    os_user: str,
    path: str,
) -> str:
    lines = [
        "**未授权使用记录（强关联）**",
        "",
        f"- 时间（洛杉矶 America/Los_Angeles）: `{time_la}`",
        f"- 稳定机器ID (OS): `{stable_id or '(未取到)'}`",
        f"- 主机名: `{hostname}`",
        f"- 关联指纹 SHA256: `{fp}`",
        f"- 访问端 IP: `{client_ip}`",
        f"- User-Agent: `{user_agent}`",
        f"- 服务进程用户: `{os_user}`",
        f"- 首次请求路径: `{path}`",
    ]
    return "\n".join(lines)


def report_if_enabled(http_ctx: Optional[Dict[str, str]] = None) -> None:
    _ensure_dotenv()
    if not _env_on("TELEMETRY_GITHUB_ENABLE"):
        return
    token = (
        os.environ.get("GITHUB_TELEMETRY_TOKEN")
        or os.environ.get("GITHUB_TOKEN")
        or ""
    ).strip()
    repo = normalize_github_repo(os.environ.get("GITHUB_TELEMETRY_REPO", ""))
    issue = os.environ.get("GITHUB_TELEMETRY_ISSUE", "").strip()
    has_gh = bool(token and repo and "/" in repo and issue.isdigit())
    has_backup = bool(
        os.environ.get("TELEMETRY_BACKUP_URL", "").strip()
        and (os.environ.get("TELEMETRY_BACKUP_SECRET") or "").strip()
    )
    if not has_gh and not has_backup:
        _log_skip(
            "已开启 TELEMETRY_GITHUB_ENABLE：需配置 GitHub（Token + GITHUB_TELEMETRY_REPO + GITHUB_TELEMETRY_ISSUE）"
            " 或 备用 TELEMETRY_BACKUP_URL + TELEMETRY_BACKUP_SECRET。"
        )
        return

    http_ctx = http_ctx or {}
    client_ip = http_ctx.get("client_ip") or ""
    user_agent = http_ctx.get("user_agent") or ""
    path = http_ctx.get("path") or ""

    sid = stable_machine_id()
    hostname = platform.node() or ""
    fp = association_fingerprint()
    os_user = process_os_user()

    if _is_whitelisted(fp, sid, client_ip, hostname):
        _log_skip("白名单命中，不推送记录。")
        return

    try:
        interval = float(os.environ.get("TELEMETRY_INTERVAL_SECONDS", "86400"))
    except ValueError:
        interval = 86400.0

    state = _load_state()
    now = time.time()
    last = float(state.get("last_report_ts") or 0)
    if (
        last
        and (now - last) < interval
        and not _env_on("TELEMETRY_FORCE")
    ):
        _log_skip(
            f"节流：距上次成功上报约 {now - last:.0f} 秒，未满 {interval:.0f} 秒，已跳过。"
            f"可删除状态文件后重试: {_STATE_PATH} ，或设 TELEMETRY_FORCE=1 / TELEMETRY_INTERVAL_SECONDS=0"
        )
        return

    time_la = _format_time_los_angeles()
    payload: Dict[str, Any] = {
        "time_la": time_la,
        "stable_machine_id": sid,
        "association_fingerprint": fp,
        "client_ip": client_ip,
        "user_agent": user_agent,
        "hostname": hostname,
        "path": path,
        "os_user": os_user,
    }
    backup_ok = _post_signed_backup(payload)

    import requests

    gh_ok = False
    if has_gh:
        body = _build_body(
            time_la, sid, hostname, fp, client_ip, user_agent, os_user, path
        )
        url = f"https://api.github.com/repos/{repo}/issues/{issue}/comments"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        try:
            r = requests.post(url, headers=headers, json={"body": body}, timeout=25)
            if r.status_code in (200, 201):
                gh_ok = True
                web = f"https://github.com/{repo}/issues/{issue}"
                print(
                    f"[telemetry_github] OK，评论已写入。浏览器打开查看: {web}",
                    flush=True,
                )
            else:
                web = f"https://github.com/{repo}/issues/{issue}"
                print(
                    f"[telemetry_github] API {r.status_code} {r.text[:400]}",
                    flush=True,
                )
                if r.status_code == 404:
                    print(
                        f"[telemetry_github] 若浏览器打开也 404，请核对：仓库是否存在、Issue #{issue} 是否未删除、"
                        f"私有仓库是否已登录有权限。应对照网页: {web}",
                        flush=True,
                    )
        except Exception as e:
            print(f"[telemetry_github] GitHub: {e}", flush=True)

    if gh_ok or backup_ok:
        state["last_report_ts"] = now
        state["last_stable_id"] = sid
        _save_state(state)


_telemetry_lock = threading.Lock()
_telemetry_started = False


def schedule_report_on_first_request(request: Any) -> None:
    """首次 HTTP 请求时采集访问端信息并后台上报（强关联依赖 IP/UA）。"""
    global _telemetry_started
    if _telemetry_started:
        return
    with _telemetry_lock:
        if _telemetry_started:
            return
        _telemetry_started = True

    ctx = {
        "client_ip": client_ip_from_request(request),
        "user_agent": (request.headers.get("User-Agent") or "")[:900],
        "path": (request.path or "")[:300],
    }

    print(
        "[telemetry_github] 已捕获首个 HTTP 请求，后台上报中…",
        flush=True,
    )

    def _run() -> None:
        try:
            report_if_enabled(ctx)
        except Exception as e:
            print(f"[telemetry_github] {e}", flush=True)

    threading.Thread(target=_run, daemon=True).start()


def diagnose() -> None:
    """在终端运行: python -c "from telemetry_github import diagnose; diagnose()" """
    _ensure_dotenv()
    print("[telemetry_github] 诊断（不发送请求、不打印 Token）:", flush=True)
    print(f"  TELEMETRY_GITHUB_ENABLE={os.environ.get('TELEMETRY_GITHUB_ENABLE', '(未设)')}", flush=True)
    print(f"  GITHUB_TELEMETRY_REPO={os.environ.get('GITHUB_TELEMETRY_REPO', '(未设)')}", flush=True)
    print(f"  GITHUB_TELEMETRY_ISSUE={os.environ.get('GITHUB_TELEMETRY_ISSUE', '(未设)')}", flush=True)
    tok = os.environ.get("GITHUB_TELEMETRY_TOKEN") or os.environ.get("GITHUB_TOKEN")
    print(f"  Token: {'已设置' if (tok and tok.strip()) else '未设置'}", flush=True)
    bu = os.environ.get("TELEMETRY_BACKUP_URL", "").strip()
    bs = (os.environ.get("TELEMETRY_BACKUP_SECRET") or "").strip()
    print(
        f"  备用 Webhook: {'已配置 URL+SECRET' if (bu and bs) else '未配置'}",
        flush=True,
    )
    print(
        f"  TRUST_PROXY_HEADERS: {os.environ.get('TRUST_PROXY_HEADERS', '(未设)')}",
        flush=True,
    )
    print(f"  状态文件: {_STATE_PATH} 存在={os.path.isfile(_STATE_PATH)}", flush=True)
    if os.path.isfile(_STATE_PATH):
        try:
            st = _load_state()
            ts = st.get("last_report_ts")
            if ts:
                age = time.time() - float(ts)
                print(f"  上次成功上报: 约 {age:.0f} 秒前", flush=True)
        except Exception:
            pass
    fp = association_fingerprint()
    sid = stable_machine_id()
    hn = platform.node() or ""
    print(f"  本机关联指纹(白名单): {fp}", flush=True)
    print(f"  本机稳定机器ID(白名单): {sid or '(无)'}", flush=True)
    print(f"  本机主机名(白名单): {hn}", flush=True)
    wl = _is_whitelisted(fp, sid, "", hn)
    print(f"  当前是否命中白名单(未计访问IP): {'是' if wl else '否'}", flush=True)


if __name__ == "__main__":
    import sys

    _ensure_dotenv()
    if len(sys.argv) >= 2 and sys.argv[1] == "send":
        os.environ["TELEMETRY_FORCE"] = "1"
        report_if_enabled(
            {
                "client_ip": "127.0.0.1",
                "user_agent": "python telemetry_github.py send",
                "path": "/",
            }
        )
    elif len(sys.argv) >= 2 and sys.argv[1] == "show":
        print("复制到 .env（按需选一或多项，逗号可添加多台）：", flush=True)
        print(f"TELEMETRY_WHITELIST_FINGERPRINTS={association_fingerprint()}", flush=True)
        print(f"TELEMETRY_WHITELIST_MACHINE_IDS={stable_machine_id()}", flush=True)
        print(f"TELEMETRY_WHITELIST_HOSTNAMES={platform.node() or ''}", flush=True)
    else:
        diagnose()
