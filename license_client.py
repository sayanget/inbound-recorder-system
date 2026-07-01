# Copyright (c) 2026 Fan Yang. All rights reserved.
"""
业务应用侧：调用独立 LICENSE 服务做在线校验。

环境变量:
  LICENSE_SERVER_URL
  LICENSE_DEVICE_TOKEN（优先；否则读 system_config.license_device_token）
  LICENSE_ENFORCE — 见 single_app._license_enforce_gate
  LICENSE_VERIFY_CACHE_SECONDS — 校验缓存秒数，0=每次请求都问许可服务，默认 300
  LICENSE_GRACE_HOURS — 许可服务不可达时的宽限小时，默认 24（仅网络/超时类失败）
  LICENSE_NO_GRACE_ERRORS — 命中则不走宽限，默认 revoked,device_revoked,expired,invalid_token
  LICENSE_GRACE_ON_REVOKE — 1 时吊销/过期也允许宽限（旧行为），默认关
  LICENSE_SERVER_PREFER_LOOPBACK — 默认 1：同机部署时若 URL 为内网 IP，自动再试 127.0.0.1
"""
from __future__ import annotations

import hashlib
import ipaddress
import os
import socket
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import requests

_verify_cache: Dict[str, Any] = {
    "ok": None,
    "reason": "unconfigured",
    "detail": {},
    "checked_at": 0.0,
}
_last_ok_at: float = 0.0
_last_working_base: str = ""


def _cache_ttl() -> float:
    try:
        return max(0.0, float(os.environ.get("LICENSE_VERIFY_CACHE_SECONDS", "300")))
    except (TypeError, ValueError):
        return 300.0


def _no_grace_errors() -> set:
    raw = os.environ.get(
        "LICENSE_NO_GRACE_ERRORS",
        "revoked,device_revoked,expired,invalid_token",
    )
    return {x.strip() for x in raw.split(",") if x.strip()}


def _grace_on_revoke_enabled() -> bool:
    return (os.environ.get("LICENSE_GRACE_ON_REVOKE") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def _grace_seconds() -> float:
    try:
        hours = float(os.environ.get("LICENSE_GRACE_HOURS", "24"))
    except (TypeError, ValueError):
        hours = 24.0
    return max(0.0, hours) * 3600.0


def _prefer_loopback_enabled() -> bool:
    return (os.environ.get("LICENSE_SERVER_PREFER_LOOPBACK") or "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def _normalize_license_url(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    if "://" not in s:
        s = "http://" + s
    return s.rstrip("/")


def _is_loopback_host(host: str) -> bool:
    h = (host or "").strip().lower()
    if h in ("localhost", "127.0.0.1", "::1"):
        return True
    try:
        return ipaddress.ip_address(h).is_loopback
    except ValueError:
        return False


def _is_private_lan_host(host: str) -> bool:
    h = (host or "").strip().lower()
    if not h or _is_loopback_host(h):
        return False
    try:
        ip = ipaddress.ip_address(h)
        return ip.is_private and not ip.is_loopback
    except ValueError:
        return False


def _rewrite_license_url_host(raw: str, new_host: str) -> str:
    parsed = urlparse(_normalize_license_url(raw))
    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "https" else 8088
    netloc = f"{new_host}:{port}" if port else new_host
    return urlunparse(
        (parsed.scheme or "http", netloc, parsed.path or "", "", parsed.query, "")
    ).rstrip("/")


def license_server_url_configured() -> str:
    return _normalize_license_url(os.environ.get("LICENSE_SERVER_URL") or "")


def license_server_url_candidates() -> List[str]:
    """可尝试的许可服务根 URL（同机时内网 IP 会追加 127.0.0.1 / localhost）。"""
    raw = license_server_url_configured()
    if not raw:
        return []
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    port = parsed.port or (443 if parsed.scheme == "https" else 8088)
    scheme = parsed.scheme or "http"

    out: List[str] = []

    def add(u: str) -> None:
        u = (u or "").rstrip("/")
        if u and u not in out:
            out.append(u)

    add(raw)
    if _prefer_loopback_enabled() and _is_private_lan_host(host):
        add(_rewrite_license_url_host(raw, "127.0.0.1"))
        add(_rewrite_license_url_host(raw, "localhost"))
    elif _prefer_loopback_enabled() and host and not _is_loopback_host(host):
        try:
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            local_ips = set()
            for info in socket.getaddrinfo(socket.gethostname(), None):
                try:
                    local_ips.add(info[4][0])
                except (IndexError, TypeError):
                    pass
            for info in infos:
                try:
                    resolved = info[4][0]
                except (IndexError, TypeError):
                    continue
                if resolved in local_ips or resolved.startswith("127."):
                    add(_rewrite_license_url_host(raw, "127.0.0.1"))
                    add(_rewrite_license_url_host(raw, "localhost"))
                    break
        except OSError:
            pass
    return out


def license_server_url_effective() -> str:
    if _last_working_base:
        return _last_working_base
    cands = license_server_url_candidates()
    return cands[0] if cands else ""


def probe_license_server(timeout: float = 2.0) -> Tuple[bool, str, str]:
    """GET /health；返回 (可达, 实际使用的 base, 错误说明)。"""
    global _last_working_base
    last_err = ""
    for base in license_server_url_candidates():
        try:
            r = requests.get(f"{base}/health", timeout=timeout)
            if r.status_code == 200:
                try:
                    js = r.json()
                    if js.get("ok"):
                        _last_working_base = base
                        return True, base, ""
                except Exception:
                    _last_working_base = base
                    return True, base, ""
            last_err = f"http_{r.status_code} @ {base}"
        except Exception as e:
            last_err = f"{e} @ {base}"
    return False, "", last_err or "no candidates"


def _license_post(path: str, payload: dict, timeout: float) -> Tuple[requests.Response, str]:
    global _last_working_base
    last_exc: Optional[Exception] = None
    for base in license_server_url_candidates():
        try:
            r = requests.post(
                f"{base}{path}",
                json=payload,
                timeout=timeout,
            )
            _last_working_base = base
            return r, base
        except requests.RequestException as e:
            last_exc = e
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("LICENSE_SERVER_URL not set")


def device_fingerprint() -> str:
    """部署实例稳定指纹（非硬件序列号，用于绑定激活名额）。"""
    parts = [
        (os.environ.get("APP_FINGERPRINT") or "inbound-recorder").strip(),
        socket.gethostname() or "host",
        (os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_PATH") or "")[:64],
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]


def resolve_device_token() -> str:
    tok = (os.environ.get("LICENSE_DEVICE_TOKEN") or "").strip()
    if tok:
        return tok
    try:
        from single_app import _get_system_config_value, get_db

        conn = get_db()
        cur = conn.cursor()
        v = _get_system_config_value(cur, "license_device_token", "")
        conn.close()
        return (v or "").strip()
    except Exception:
        return ""


def _verify_remote(token: str) -> Tuple[bool, str, Dict[str, Any]]:
    if not license_server_url_configured() or not token:
        return True, "unconfigured", {}
    try:
        r, _base = _license_post(
            "/v1/verify",
            {"device_token": token},
            timeout=15,
        )
        ct = r.headers.get("content-type") or ""
        js = r.json() if "application/json" in ct else {}
        if r.status_code == 200 and js.get("ok"):
            detail = {
                k: js.get(k)
                for k in ("license_id", "label", "expires_at", "max_activations")
                if k in js
            }
            return True, "ok", detail
        err = js.get("error") or f"http_{r.status_code}"
        return False, str(err), {}
    except Exception as e:
        return False, str(e), {}


def verify_license() -> Tuple[bool, str]:
    """返回 (是否通过, 原因码或说明)。"""
    global _last_ok_at, _verify_cache

    token = resolve_device_token()
    if not license_server_url_configured() or not token:
        _verify_cache = {
            "ok": True,
            "reason": "unconfigured",
            "detail": {},
            "checked_at": time.time(),
        }
        return True, "unconfigured"

    now = time.time()
    ttl = _cache_ttl()
    if (
        ttl > 0
        and _verify_cache.get("checked_at")
        and (now - float(_verify_cache["checked_at"])) < ttl
        and _verify_cache.get("ok") is not None
    ):
        return bool(_verify_cache["ok"]), str(_verify_cache.get("reason") or "")

    ok, reason, detail = _verify_remote(token)
    _verify_cache = {
        "ok": ok,
        "reason": reason,
        "detail": detail,
        "checked_at": now,
    }
    if ok:
        _last_ok_at = now
        return True, reason

    hard_fail = reason in _no_grace_errors() and not _grace_on_revoke_enabled()
    if not hard_fail:
        grace = _grace_seconds()
        if grace > 0 and _last_ok_at and (now - _last_ok_at) < grace:
            return True, "grace_period"

    return False, reason


def activate_license(
    license_key: str, fingerprint: Optional[str] = None
) -> Tuple[bool, str, dict]:
    """首次/重新激活：成功时响应含 device_token。"""
    if not license_server_url_configured():
        return False, "LICENSE_SERVER_URL not set", {}
    fp = (fingerprint or device_fingerprint()).strip()
    try:
        r, _base = _license_post(
            "/v1/activate",
            {
                "license_key": license_key.strip(),
                "device_fingerprint": fp[:128],
            },
            timeout=20,
        )
        js = r.json() if r.content else {}
        if r.status_code == 200 and js.get("ok"):
            global _last_ok_at, _verify_cache
            _last_ok_at = time.time()
            _verify_cache = {
                "ok": True,
                "reason": "ok",
                "detail": {
                    k: js.get(k)
                    for k in ("label", "expires_at")
                    if js.get(k) is not None
                },
                "checked_at": _last_ok_at,
            }
            return True, "", js
        return False, str(js.get("error") or r.text), js
    except Exception as e:
        return False, str(e), {}


def license_status() -> dict:
    """供 /api/license_status 与管理员面板。"""
    en = (os.environ.get("LICENSE_ENFORCE") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    configured_url = license_server_url_configured()
    tok = resolve_device_token()
    configured = bool(configured_url and tok)
    fp = device_fingerprint()
    reachable, eff_url, probe_err = probe_license_server() if configured_url else (
        False,
        "",
        "",
    )

    if not configured:
        return {
            "enforced": en,
            "configured": False,
            "ok": True,
            "reason": "unconfigured",
            "ready_for_enforce": False,
            "device_fingerprint": fp,
            "token_from_env": bool((os.environ.get("LICENSE_DEVICE_TOKEN") or "").strip()),
            "expires_at": None,
            "label": None,
            "server_url": configured_url,
            "server_url_effective": eff_url,
            "server_reachable": reachable,
            "server_probe_error": probe_err,
        }

    ok, reason = verify_license()
    detail = _verify_cache.get("detail") or {}
    return {
        "enforced": en,
        "configured": True,
        "ok": ok,
        "reason": reason,
        "ready_for_enforce": bool(ok),
        "device_fingerprint": fp,
        "token_from_env": bool((os.environ.get("LICENSE_DEVICE_TOKEN") or "").strip()),
        "expires_at": detail.get("expires_at"),
        "label": detail.get("label"),
        "cache_age_seconds": int(time.time() - float(_verify_cache.get("checked_at") or 0)),
        "server_url": configured_url,
        "server_url_effective": license_server_url_effective() or eff_url,
        "server_reachable": reachable,
        "server_probe_error": probe_err,
        "server_url_candidates": license_server_url_candidates(),
        "policy": {
            "verify_cache_seconds": int(_cache_ttl()),
            "grace_hours": _grace_seconds() / 3600.0,
            "grace_on_revoke": _grace_on_revoke_enabled(),
            "no_grace_errors": sorted(_no_grace_errors()),
            "prefer_loopback": _prefer_loopback_enabled(),
        },
    }


def invalidate_verify_cache() -> None:
    global _verify_cache
    _verify_cache["checked_at"] = 0.0


def _tcp_can_bind(host: str, port: int) -> bool:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        finally:
            s.close()
    except OSError:
        return False


def resolve_license_bind_port(
    preferred: Optional[int] = None,
    avoid: Optional[set[int]] = None,
) -> int:
    """Windows Hyper-V 常保留 8066–8165，8088 无法绑定时自动换端口。"""
    try:
        port = int(preferred if preferred is not None else _license_bind_port())
    except (TypeError, ValueError):
        port = 8088
    blocked = avoid or set()
    if port not in blocked and _tcp_can_bind("0.0.0.0", port):
        return port
    fallbacks = (18088, 19088, 28188, 38888, 48888)
    for p in (port,) + fallbacks:
        if p in blocked:
            continue
        if _tcp_can_bind("0.0.0.0", p):
            if p != port:
                print(
                    f"[LICENSE] Port {port} unavailable (reserved or in use); "
                    f"using LICENSE_BIND_PORT={p}",
                    flush=True,
                )
            return p
    return port


def sync_license_server_url_env(port: int) -> None:
    """LICENSE_SERVER_URL 端口与 LICENSE_BIND_PORT 对齐（同机 loopback）。"""
    url = (os.environ.get("LICENSE_SERVER_URL") or "").strip()
    if not url:
        os.environ["LICENSE_SERVER_URL"] = f"http://127.0.0.1:{port}"
        return
    try:
        parsed = urlparse(url)
        if parsed.hostname in ("127.0.0.1", "localhost", "::1"):
            new_netloc = f"{parsed.hostname}:{port}"
            os.environ["LICENSE_SERVER_URL"] = urlunparse(
                (parsed.scheme, new_netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
            )
    except Exception:
        pass


def _license_bind_port() -> int:
    try:
        return int(os.environ.get("LICENSE_BIND_PORT", "8088"))
    except (TypeError, ValueError):
        return 8088


def _license_auto_start_enabled() -> bool:
    if (os.environ.get("LICENSE_AUTO_START_SERVER") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    ):
        return True
    return (os.environ.get("LICENSE_ENFORCE") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def is_license_server_port_open(port: Optional[int] = None) -> bool:
    port = port if port is not None else _license_bind_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def ensure_license_server_running(wait_seconds: float = 15.0) -> bool:
    """同机未监听许可端口时拉起 license_server.app（LICENSE_ENFORCE / LICENSE_AUTO_START_SERVER）。"""
    avoid = set()
    for key in ("PORT", "APP_PORT", "MONITOR_PORT"):
        raw = (os.environ.get(key) or "").strip()
        if raw.isdigit():
            avoid.add(int(raw))
    port = resolve_license_bind_port(_license_bind_port(), avoid)
    os.environ["LICENSE_BIND_PORT"] = str(port)
    sync_license_server_url_env(port)
    if not _license_auto_start_enabled():
        return is_license_server_port_open(port)
    if is_license_server_port_open(port):
        return True
    root = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(root, "license_server_stdout.log")
    python_cmd = sys.executable or "python"
    env = os.environ.copy()
    env.setdefault("LICENSE_BIND_HOST", "0.0.0.0")
    env["LICENSE_BIND_PORT"] = str(port)
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        with open(log_path, "a", encoding="utf-8") as logf:
            logf.write(f"\n--- License server auto-start {time.ctime()} ---\n")
            logf.flush()
            flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            subprocess.Popen(
                [python_cmd, "-m", "license_server.app"],
                stdout=logf,
                stderr=logf,
                cwd=root,
                env=env,
                creationflags=flags,
            )
    except Exception:
        return False
    deadline = time.time() + max(1.0, wait_seconds)
    while time.time() < deadline:
        if is_license_server_port_open(port):
            return True
        time.sleep(0.5)
    return is_license_server_port_open(port)


def bootstrap_license_server_at_startup() -> bool:
    """业务进程启动时调用一次；失败时打印提示，不阻断 import。"""
    if not _license_auto_start_enabled():
        return is_license_server_port_open()
    if not (os.environ.get("LICENSE_SERVER_URL") or "").strip():
        return False
    ok = ensure_license_server_running()
    if not ok:
        print(
            f"[LICENSE] 许可服务 127.0.0.1:{_license_bind_port()} 未就绪；"
            "请运行 run_license_server.bat 或 start_with_monitor.bat",
            flush=True,
        )
    return ok
