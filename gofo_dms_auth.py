"""
GoFO DMS (dms.gofoexpress.com) captcha login — shared by scripts/gofo_login_token.py and single_app admin API.

Password is AES-CBC encrypted to match static/js/usePrivacy.*.js (export Q).
Requires: pip install pycryptodome requests
"""
from __future__ import annotations

import base64
import os
from typing import Any, Dict, Optional, Tuple

import requests
from requests.utils import dict_from_cookiejar

try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
except ImportError:
    AES = None  # type: ignore[misc, assignment]
    pad = None  # type: ignore[misc, assignment]

_GOFO_LOGIN_AES_KEY = "59SO+p2dXTeghIqm"


def get_gofo_api_base() -> str:
    return os.environ.get("GOFO_API_BASE", "https://dms.gofoexpress.com/prod-api").rstrip("/")


def encrypt_password_dms(plain: str) -> str:
    if AES is None or pad is None:
        raise RuntimeError("Install pycryptodome: pip install pycryptodome")
    key = _GOFO_LOGIN_AES_KEY.encode("utf-8")
    iv = key
    cipher = AES.new(key, AES.MODE_CBC, iv)
    raw = pad(plain.encode("utf-8"), AES.block_size)
    return base64.b64encode(cipher.encrypt(raw)).decode("ascii")


def new_dms_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (compatible; InboundGofo/1.0)",
            "Accept": "application/json, text/plain, */*",
        }
    )
    return s


def session_cookies_dict(sess: requests.Session) -> Dict[str, str]:
    return dict_from_cookiejar(sess.cookies)


def apply_cookies_dict(sess: requests.Session, cookies: Dict[str, str]) -> None:
    sess.cookies.clear()
    for name, value in cookies.items():
        sess.cookies.set(name, value)


def fetch_captcha(sess: requests.Session, base: Optional[str] = None) -> Tuple[str, str]:
    """GET captchaImage. Returns (uuid, img) — img is raw base64 from API (no data: prefix)."""
    b = base or get_gofo_api_base()
    r = sess.get(f"{b}/captchaImage", timeout=20)
    r.raise_for_status()
    cap = r.json()
    if cap.get("code") != 200:
        raise ValueError(cap.get("msg") or str(cap))
    u = cap.get("uuid")
    img = cap.get("img")
    if not u or not img:
        raise ValueError("captchaImage missing uuid or img")
    return str(u), str(img)


def login_dms(
    sess: requests.Session,
    *,
    base: Optional[str],
    uuid: str,
    username: str,
    password_plain: str,
    captcha_code: str,
    plain_password: bool = False,
) -> Dict[str, Any]:
    b = base or get_gofo_api_base()
    pwd_out = password_plain if plain_password else encrypt_password_dms(password_plain)
    payload = {
        "username": username.replace(" ", ""),
        "password": pwd_out,
        "code": captcha_code.strip(),
        "uuid": uuid,
        "rememberMe": False,
    }
    r = sess.post(
        f"{b}/login",
        json=payload,
        headers={"Content-Type": "application/json;charset=UTF-8"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def extract_jwt_from_login_body(body: Dict[str, Any]) -> Optional[str]:
    if not isinstance(body, dict):
        return None
    for key in ("token", "access_token", "accessToken"):
        v = body.get(key)
        if isinstance(v, str) and v.count(".") == 2:
            return v
    data = body.get("data")
    if isinstance(data, str) and data.count(".") == 2:
        return data
    if isinstance(data, dict):
        for key in ("token", "access_token", "accessToken"):
            v = data.get(key)
            if isinstance(v, str) and v.count(".") == 2:
                return v
    return None


def decode_captcha_image_bytes(img: str) -> bytes:
    raw = img.strip()
    if raw.startswith("data:") and "," in raw:
        raw = raw.split(",", 1)[1]
    return base64.b64decode(raw)
