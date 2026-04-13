"""
Log in to GoFO DMS (captcha + AES password) and print or save the JWT.

Env (recommended):
  GOFO_USERNAME, GOFO_PASSWORD

Usage:
  python scripts/gofo_login_token.py
  python scripts/gofo_login_token.py --no-save
  python scripts/gofo_login_token.py --captcha AB12

See gofo_dms_auth.py for crypto and API details.
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import tempfile
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import requests

from gofo_dms_auth import (
    decode_captcha_image_bytes,
    extract_jwt_from_login_body,
    fetch_captcha,
    get_gofo_api_base,
    login_dms,
    new_dms_session,
)

BASE = get_gofo_api_base()


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch GoFO DMS JWT via captcha login.")
    parser.add_argument("--username", default=os.environ.get("GOFO_USERNAME", "").strip())
    parser.add_argument("--password", default=os.environ.get("GOFO_PASSWORD", "").strip())
    parser.add_argument("--captcha", default="", help="Captcha text (otherwise prompt)")
    parser.add_argument("--no-save", action="store_true", help="Do not write gofo_token.txt")
    parser.add_argument("--output", default="", help="Write token to this file (default: repo root gofo_token.txt)")
    parser.add_argument("--open-image", action="store_true", help="Open captcha image with default viewer (Windows)")
    parser.add_argument(
        "--plain-password",
        action="store_true",
        help="Send password without AES (only if your tenant does not use web encryption)",
    )
    args = parser.parse_args()

    username = args.username
    password = args.password
    if not username:
        username = input("GOFO username: ").strip()
    if not password:
        password = getpass.getpass("GOFO password: ")

    session = new_dms_session()

    try:
        uuid, img_b64 = fetch_captcha(session, BASE)
    except (requests.RequestException, ValueError, json.JSONDecodeError) as e:
        print(f"captchaImage failed: {e}", file=sys.stderr)
        return 2

    img_bytes = decode_captcha_image_bytes(img_b64)
    tmp = tempfile.NamedTemporaryFile(suffix=".png", prefix="gofo_captcha_", delete=False)
    try:
        tmp.write(img_bytes)
        tmp.flush()
        tmp_path = Path(tmp.name)
    finally:
        tmp.close()
    print(f"Captcha image: {tmp_path}", file=sys.stderr)
    if args.open_image:
        try:
            os.startfile(str(tmp_path))  # type: ignore[attr-defined]
        except OSError:
            pass

    captcha = (args.captcha or "").strip()
    if not captcha:
        captcha = input("Enter captcha (from image): ").strip()

    try:
        body = login_dms(
            session,
            base=BASE,
            uuid=uuid,
            username=username,
            password_plain=password,
            captcha_code=captcha,
            plain_password=args.plain_password,
        )
    except (requests.RequestException, json.JSONDecodeError) as e:
        print(f"login request failed: {e}", file=sys.stderr)
        return 3

    if body.get("code") != 200:
        print(json.dumps(body, ensure_ascii=False, indent=2), file=sys.stderr)
        return 4

    token = extract_jwt_from_login_body(body)
    if not token:
        print("Login OK but could not find JWT in response:", file=sys.stderr)
        print(json.dumps(body, ensure_ascii=False, indent=2), file=sys.stderr)
        return 5

    print(token)

    if not args.no_save:
        out = Path(args.output) if args.output else _ROOT / "gofo_token.txt"
        try:
            out.write_text(token.strip() + "\n", encoding="utf-8")
            print(f"Wrote token to {out}", file=sys.stderr)
        except OSError as e:
            print(f"Could not write {out}: {e}", file=sys.stderr)
            return 6

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
