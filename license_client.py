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
"""
from __future__ import annotations

import hashlib
import os
import socket
import time
from typing import Any, Dict, Optional, Tuple

import requests

_verify_cache: Dict[str, Any] = {
    "ok": None,
    "reason": "unconfigured",
    "detail": {},
    "checked_at": 0.0,
}
_last_ok_at: float = 0.0


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


def _license_server_url() -> str:
    return (os.environ.get("LICENSE_SERVER_URL") or "").strip().rstrip("/")


def _verify_remote(token: str) -> Tuple[bool, str, Dict[str, Any]]:
    base = _license_server_url()
    if not base or not token:
        return True, "unconfigured", {}
    try:
        r = requests.post(
            f"{base}/v1/verify",
            json={"device_token": token},
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
    base = _license_server_url()
    if not base or not token:
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
    base = _license_server_url()
    if not base:
        return False, "LICENSE_SERVER_URL not set", {}
    fp = (fingerprint or device_fingerprint()).strip()
    try:
        r = requests.post(
            f"{base}/v1/activate",
            json={
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
    base = _license_server_url()
    tok = resolve_device_token()
    configured = bool(base and tok)
    fp = device_fingerprint()

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
        "policy": {
            "verify_cache_seconds": int(_cache_ttl()),
            "grace_hours": _grace_seconds() / 3600.0,
            "grace_on_revoke": _grace_on_revoke_enabled(),
            "no_grace_errors": sorted(_no_grace_errors()),
        },
    }


def invalidate_verify_cache() -> None:
    global _verify_cache
    _verify_cache["checked_at"] = 0.0
