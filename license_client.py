"""
业务应用侧：调用独立 LICENSE 服务做在线校验。

环境变量:
  LICENSE_SERVER_URL   例如 http://127.0.0.1:8088
  LICENSE_DEVICE_TOKEN 由 /v1/activate 返回，写入 .env

未配置 URL 或 TOKEN 时 verify_license() 返回 (True, "unconfigured")，不阻断（便于开发）。
默认不设置 LICENSE_ENFORCE；上线前用 /api/license_status 查看 ready_for_enforce 再打开强制。
"""
from __future__ import annotations

import os
from typing import Tuple

import requests


def verify_license() -> Tuple[bool, str]:
    """
    返回 (是否通过, 原因码或说明)。
    """
    base = (os.environ.get("LICENSE_SERVER_URL") or "").strip().rstrip("/")
    token = (os.environ.get("LICENSE_DEVICE_TOKEN") or "").strip()
    if not base or not token:
        return True, "unconfigured"

    try:
        r = requests.post(
            f"{base}/v1/verify",
            json={"device_token": token},
            timeout=15,
        )
        ct = r.headers.get("content-type") or ""
        js = r.json() if "application/json" in ct else {}
        if r.status_code == 200 and js.get("ok"):
            return True, "ok"
        err = js.get("error") or f"http_{r.status_code}"
        return False, str(err)
    except Exception as e:
        return False, str(e)


def activate_license(license_key: str, device_fingerprint: str) -> Tuple[bool, str, dict]:
    """
    首次激活：返回 (成功, 错误信息, 响应 dict)。
    成功时响应含 device_token，应写入环境或安全存储。
    """
    base = (os.environ.get("LICENSE_SERVER_URL") or "").strip().rstrip("/")
    if not base:
        return False, "LICENSE_SERVER_URL not set", {}
    try:
        r = requests.post(
            f"{base}/v1/activate",
            json={
                "license_key": license_key.strip(),
                "device_fingerprint": device_fingerprint[:128],
            },
            timeout=20,
        )
        js = r.json() if r.content else {}
        if r.status_code == 200 and js.get("ok"):
            return True, "", js
        return False, str(js.get("error") or r.text), js
    except Exception as e:
        return False, str(e), {}


def license_status() -> dict:
    """
    供 /api/license_status：是否强制、是否已配置、当前是否校验通过。
    若已配置 URL+TOKEN，会请求许可服务。
    """
    en = (os.environ.get("LICENSE_ENFORCE") or "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
    base = (os.environ.get("LICENSE_SERVER_URL") or "").strip()
    tok = (os.environ.get("LICENSE_DEVICE_TOKEN") or "").strip()
    configured = bool(base and tok)
    if not configured:
        return {
            "enforced": en,
            "configured": False,
            "ok": True,
            "reason": "unconfigured",
            "ready_for_enforce": False,
        }
    ok, reason = verify_license()
    return {
        "enforced": en,
        "configured": True,
        "ok": ok,
        "reason": reason,
        "ready_for_enforce": bool(ok),
    }

