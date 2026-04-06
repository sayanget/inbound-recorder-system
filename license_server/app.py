"""
许可证 API：激活 / 校验 / 管理端签发。

运行（项目根目录）:
  set LICENSE_ADMIN_KEY=你的长随机串
  python -m license_server.app
或:
  flask --app license_server.app run --host 0.0.0.0 --port 8088

PostgreSQL:
  set LICENSE_DATABASE_URL=postgresql+psycopg2://user:pass@host:5432/dbname

根路径与管理页: http://127.0.0.1:8088/ 或 /admin ；健康检查: /health
"""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from license_server.db import SessionLocal, init_db
from license_server.models import Device, License

app = Flask(__name__)
# 会话密钥：务必固定 LICENSE_WEB_SECRET（随机长串），否则勿频繁改 LICENSE_ADMIN_KEY，否则全员登出
app.secret_key = os.environ.get("LICENSE_WEB_SECRET") or hashlib.sha256(
    (os.environ.get("LICENSE_ADMIN_KEY") or "license-web-dev").encode("utf-8")
).hexdigest()
_session_days = int(os.environ.get("LICENSE_SESSION_DAYS", "90"))
_session_days = max(1, min(_session_days, 365))
app.permanent_session_lifetime = timedelta(days=_session_days)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# 仅 HTTPS 部署时设 LICENSE_SESSION_SECURE=1
if (os.environ.get("LICENSE_SESSION_SECURE") or "").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
):
    app.config["SESSION_COOKIE_SECURE"] = True


@app.before_request
def _refresh_admin_session_cookie():
    """已登录管理页时每次请求续期 Cookie（滑动过期），减少无故掉线。"""
    path = request.path or ""
    if not path.startswith("/admin"):
        return
    if path.startswith("/admin/login") and request.method == "POST":
        return
    if session.get("license_admin_ok"):
        session.permanent = True
        session.modified = True


def _hash_license_key(raw: str) -> str:
    s = raw.strip()
    pepper = os.environ.get("LICENSE_KEY_PEPPER", "inbound-license-v1")
    return hashlib.sha256(f"{pepper}|{s}".encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """SQLite 常返回 naive datetime，统一按 UTC 比较。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _admin_ok() -> bool:
    want = (os.environ.get("LICENSE_ADMIN_KEY") or "").strip()
    got = (request.headers.get("X-Admin-Key") or "").strip()
    return bool(want) and secrets.compare_digest(want, got)


def _admin_session_ok() -> bool:
    return bool(session.get("license_admin_ok"))


def _verify_admin_key_plain(key: str) -> bool:
    want = (os.environ.get("LICENSE_ADMIN_KEY") or "").strip()
    return bool(want) and secrets.compare_digest(want, key.strip())


def _list_licenses_rows():
    db = SessionLocal()
    try:
        rows = db.query(License).order_by(License.id.desc()).all()
        out = []
        for lic in rows:
            cnt = (
                db.query(Device)
                .filter(Device.license_id == lic.id, Device.revoked_at.is_(None))
                .count()
            )
            out.append(
                {
                    "id": lic.id,
                    "label": lic.label,
                    "max_activations": lic.max_activations,
                    "expires_at": _as_utc_aware(lic.expires_at),
                    "revoked_at": _as_utc_aware(lic.revoked_at),
                    "devices_active": cnt,
                }
            )
        return out
    finally:
        db.close()


def _create_license_record(
    label: Optional[str],
    max_act: int,
    expires_in_days: Optional[int],
) -> dict:
    try:
        ma = int(max_act)
    except (TypeError, ValueError):
        ma = 1
    ma = max(1, min(ma, 9999))
    exp: Optional[datetime] = None
    if expires_in_days is not None:
        try:
            d = int(expires_in_days)
            exp = _utcnow() + timedelta(days=max(0, d))
        except (TypeError, ValueError):
            pass

    raw_key = f"INB-{secrets.token_urlsafe(24)}"
    kh = _hash_license_key(raw_key)

    db = SessionLocal()
    try:
        lic = License(
            key_hash=kh,
            label=label,
            max_activations=ma,
            expires_at=exp,
        )
        db.add(lic)
        db.commit()
        db.refresh(lic)
        return {
            "ok": True,
            "id": lic.id,
            "license_key": raw_key,
            "max_activations": lic.max_activations,
            "expires_at": _as_utc_aware(lic.expires_at).isoformat()
            if lic.expires_at
            else None,
            "note": "Save license_key now; it is not stored in plaintext.",
        }
    finally:
        db.close()


@app.route("/")
def index():
    """根路径：进入管理页（未登录则显示登录表单）。"""
    return redirect(url_for("admin_page"))


@app.route("/health")
def health():
    return jsonify({"ok": True})


@app.route("/v1/activate", methods=["POST"])
def activate():
    data = request.get_json(silent=True) or {}
    key = (data.get("license_key") or "").strip()
    fp = (data.get("device_fingerprint") or "").strip()
    if not key or not fp:
        return jsonify({"ok": False, "error": "license_key and device_fingerprint required"}), 400

    kh = _hash_license_key(key)
    db = SessionLocal()
    try:
        lic = db.query(License).filter(License.key_hash == kh).one_or_none()
        if not lic:
            return jsonify({"ok": False, "error": "invalid_license"}), 404
        if lic.revoked_at:
            return jsonify({"ok": False, "error": "revoked"}), 403
        _exp = _as_utc_aware(lic.expires_at)
        if _exp and _exp < _utcnow():
            return jsonify({"ok": False, "error": "expired"}), 403

        dev = (
            db.query(Device)
            .filter(Device.license_id == lic.id, Device.fingerprint == fp)
            .one_or_none()
        )
        active_count = (
            db.query(Device)
            .filter(Device.license_id == lic.id, Device.revoked_at.is_(None))
            .count()
        )

        if dev:
            if dev.revoked_at:
                return jsonify({"ok": False, "error": "device_revoked"}), 403
            dev.last_seen_at = _utcnow()
            db.commit()
            return jsonify(
                {
                    "ok": True,
                    "device_token": dev.device_token,
                    "expires_at": _as_utc_aware(lic.expires_at).isoformat()
                    if lic.expires_at
                    else None,
                    "label": lic.label,
                }
            )

        if active_count >= lic.max_activations:
            return jsonify({"ok": False, "error": "activation_limit"}), 403

        token = secrets.token_urlsafe(32)
        new_dev = Device(
            license_id=lic.id,
            fingerprint=fp[:128],
            device_token=token,
            last_seen_at=_utcnow(),
        )
        db.add(new_dev)
        db.commit()
        return jsonify(
            {
                "ok": True,
                "device_token": token,
                "expires_at": _as_utc_aware(lic.expires_at).isoformat()
                if lic.expires_at
                else None,
                "label": lic.label,
            }
        )
    finally:
        db.close()


@app.route("/v1/verify", methods=["POST"])
def verify():
    data = request.get_json(silent=True) or {}
    token = (data.get("device_token") or "").strip()
    if not token:
        return jsonify({"ok": False, "error": "device_token required"}), 400

    db = SessionLocal()
    try:
        dev = db.query(Device).filter(Device.device_token == token).one_or_none()
        if not dev or dev.revoked_at:
            return jsonify({"ok": False, "error": "invalid_token"}), 403
        lic = db.query(License).filter(License.id == dev.license_id).one_or_none()
        if not lic:
            return jsonify({"ok": False, "error": "invalid_license"}), 403
        if lic.revoked_at:
            return jsonify({"ok": False, "error": "revoked"}), 403
        exp = _as_utc_aware(lic.expires_at)
        if exp and exp < _utcnow():
            return jsonify({"ok": False, "error": "expired"}), 403

        dev.last_seen_at = _utcnow()
        db.commit()
        return jsonify(
            {
                "ok": True,
                "license_id": lic.id,
                "label": lic.label,
                "expires_at": _as_utc_aware(lic.expires_at).isoformat()
                if lic.expires_at
                else None,
                "max_activations": lic.max_activations,
            }
        )
    finally:
        db.close()


@app.route("/v1/admin/licenses", methods=["GET", "POST"])
def admin_licenses_api():
    if not _admin_ok():
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    if request.method == "GET":
        db = SessionLocal()
        try:
            rows = db.query(License).order_by(License.id.desc()).all()
            out = []
            for lic in rows:
                cnt = (
                    db.query(Device)
                    .filter(Device.license_id == lic.id, Device.revoked_at.is_(None))
                    .count()
                )
                out.append(
                    {
                        "id": lic.id,
                        "label": lic.label,
                        "max_activations": lic.max_activations,
                        "expires_at": _as_utc_aware(lic.expires_at).isoformat()
                        if lic.expires_at
                        else None,
                        "revoked_at": _as_utc_aware(lic.revoked_at).isoformat()
                        if lic.revoked_at
                        else None,
                        "devices_active": cnt,
                    }
                )
            return jsonify({"ok": True, "licenses": out})
        finally:
            db.close()

    data = request.get_json(silent=True) or {}
    label = (data.get("label") or "").strip() or None
    try:
        max_act = int(data.get("max_activations", 1))
    except (TypeError, ValueError):
        max_act = 1
    expires_in_days = data.get("expires_in_days")
    if expires_in_days is not None:
        try:
            expires_in_days = int(expires_in_days)
        except (TypeError, ValueError):
            expires_in_days = None
    result = _create_license_record(label, max_act, expires_in_days)
    return jsonify(result)


@app.route("/v1/admin/licenses/<int:license_id>/revoke", methods=["POST"])
def admin_revoke_license(license_id: int):
    if not _admin_ok():
        return jsonify({"ok": False, "error": "unauthorized"}), 401
    db = SessionLocal()
    try:
        lic = db.query(License).filter(License.id == license_id).one_or_none()
        if not lic:
            return jsonify({"ok": False, "error": "not_found"}), 404
        lic.revoked_at = _utcnow()
        db.commit()
        return jsonify({"ok": True})
    finally:
        db.close()


@app.route("/admin")
def admin_page():
    if not _admin_session_ok():
        return render_template(
            "admin.html",
            logged_in=False,
            error=request.args.get("e"),
        )
    return render_template(
        "admin.html",
        logged_in=True,
        licenses=_list_licenses_rows(),
    )


@app.route("/admin/login", methods=["POST"])
def admin_login():
    if not (os.environ.get("LICENSE_ADMIN_KEY") or "").strip():
        return redirect(url_for("admin_page") + "?e=1")
    key = request.form.get("admin_key", "")
    if _verify_admin_key_plain(key):
        session["license_admin_ok"] = True
        session.permanent = True
        return redirect(url_for("admin_page"))
    return redirect(url_for("admin_page") + "?e=1")


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("license_admin_ok", None)
    return redirect(url_for("admin_page"))


@app.route("/admin/licenses/create", methods=["POST"])
def admin_create_web():
    if not _admin_session_ok():
        return redirect(url_for("admin_page"))
    label = (request.form.get("label") or "").strip() or None
    try:
        max_act = int(request.form.get("max_activations") or 1)
    except ValueError:
        max_act = 1
    ex = request.form.get("expires_in_days")
    exp_days: Optional[int] = None
    if ex is not None and str(ex).strip() != "":
        try:
            exp_days = int(ex)
        except ValueError:
            flash("有效天数格式无效", "error")
            return redirect(url_for("admin_page"))
    res = _create_license_record(label, max_act, exp_days)
    if res.get("ok"):
        flash(res["license_key"], "license_key")
    return redirect(url_for("admin_page"))


@app.route("/admin/licenses/<int:license_id>/revoke", methods=["POST"])
def admin_revoke_web(license_id: int):
    if not _admin_session_ok():
        return redirect(url_for("admin_page"))
    db = SessionLocal()
    try:
        lic = db.query(License).filter(License.id == license_id).one_or_none()
        if lic and not lic.revoked_at:
            lic.revoked_at = _utcnow()
            db.commit()
    finally:
        db.close()
    return redirect(url_for("admin_page"))


def main():
    init_db()
    host = os.environ.get("LICENSE_BIND_HOST", "0.0.0.0")
    port = int(os.environ.get("LICENSE_BIND_PORT", "8088"))
    app.run(host=host, port=port, threaded=True)


if __name__ == "__main__":
    main()
