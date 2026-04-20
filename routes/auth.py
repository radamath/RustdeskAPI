"""Admin panel authentication (session-based) and helper utilities."""

import base64
import functools
import io
from datetime import datetime, timezone

import bcrypt
import jwt
import pyotp
import qrcode
from flask import Blueprint, current_app, jsonify, request, session

from models import AdminUser, AuditLog, db

bp = Blueprint("auth", __name__)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def admin_required(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        uid = session.get("admin_user_id")
        if not uid:
            return jsonify({"error": "Oturum açmanız gerekiyor"}), 401
        user = db.session.get(AdminUser, uid)
        if not user or not user.is_active:
            session.clear()
            return jsonify({"error": "Geçersiz oturum"}), 401
        request._admin_user = user
        return fn(*args, **kwargs)
    return wrapper


def log_audit(action: str, details: str = ""):
    user = getattr(request, "_admin_user", None)
    entry = AuditLog(
        admin_user_id=user.id if user else None,
        action=action,
        details=details,
        ip_address=request.remote_addr or "",
    )
    db.session.add(entry)
    db.session.commit()


# ── JWT helpers for RustDesk client tokens ──────────────────────────

def create_client_jwt(user_id: int, username: str) -> str:
    from datetime import timedelta
    exp = datetime.now(timezone.utc) + timedelta(
        hours=current_app.config["JWT_EXPIRATION_HOURS"]
    )
    return jwt.encode(
        {"user_id": user_id, "username": username, "exp": exp},
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )


def decode_client_jwt(token: str):
    try:
        return jwt.decode(
            token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
        )
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ── Admin login / logout endpoints ──────────────────────────────────

@bp.route("/admin/api/login", methods=["POST"])
def admin_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    totp_code = data.get("totp_code", "")

    user = AdminUser.query.filter_by(username=username).first()
    if not user or not check_password(password, user.password_hash):
        return jsonify({"error": "Kullanıcı adı veya şifre hatalı"}), 401

    if not user.is_active:
        return jsonify({"error": "Hesap devre dışı"}), 403

    if user.totp_enabled:
        if not totp_code:
            return jsonify({"requires_2fa": True, "error": "2FA kodu gerekli"}), 202
        totp = pyotp.TOTP(user.totp_secret)
        if not totp.verify(totp_code, valid_window=1):
            return jsonify({"error": "Geçersiz 2FA kodu"}), 401

    session.permanent = True
    session["admin_user_id"] = user.id
    log_audit("admin_login", f"Admin giriş: {username}")
    return jsonify({
        "id": user.id,
        "username": user.username,
        "email": user.email or "",
        "role": user.role,
        "totp_enabled": user.totp_enabled,
    })


@bp.route("/admin/api/logout", methods=["POST"])
@admin_required
def admin_logout():
    log_audit("admin_logout")
    session.clear()
    return jsonify({"ok": True})


@bp.route("/admin/api/me", methods=["GET"])
@admin_required
def admin_me():
    u = request._admin_user
    return jsonify({
        "id": u.id,
        "username": u.username,
        "email": u.email or "",
        "role": u.role,
        "totp_enabled": u.totp_enabled,
    })


# ── 2FA (TOTP) endpoints ────────────────────────────────────────────

@bp.route("/admin/api/2fa/setup", methods=["POST"])
@admin_required
def totp_setup():
    u = request._admin_user
    if u.totp_enabled:
        return jsonify({"error": "2FA zaten etkin"}), 400

    secret = pyotp.random_base32()
    u.totp_secret = secret
    db.session.commit()

    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=u.username, issuer_name="RustDesk Admin")

    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    return jsonify({
        "secret": secret,
        "qr_code": f"data:image/png;base64,{qr_b64}",
        "uri": uri,
    })


@bp.route("/admin/api/2fa/verify", methods=["POST"])
@admin_required
def totp_verify():
    u = request._admin_user
    data = request.get_json(silent=True) or {}
    code = data.get("code", "")

    if not u.totp_secret:
        return jsonify({"error": "Önce 2FA kurulumu yapın"}), 400

    totp = pyotp.TOTP(u.totp_secret)
    if not totp.verify(code, valid_window=1):
        return jsonify({"error": "Geçersiz kod"}), 401

    u.totp_enabled = True
    db.session.commit()
    log_audit("2fa_enabled", f"2FA etkinleştirildi: {u.username}")
    return jsonify({"ok": True})


@bp.route("/admin/api/2fa/disable", methods=["POST"])
@admin_required
def totp_disable():
    u = request._admin_user
    data = request.get_json(silent=True) or {}
    code = data.get("code", "")

    if not u.totp_enabled:
        return jsonify({"error": "2FA zaten devre dışı"}), 400

    totp = pyotp.TOTP(u.totp_secret)
    if not totp.verify(code, valid_window=1):
        return jsonify({"error": "Geçersiz kod, 2FA devre dışı bırakılamadı"}), 401

    u.totp_enabled = False
    u.totp_secret = None
    db.session.commit()
    log_audit("2fa_disabled", f"2FA devre dışı bırakıldı: {u.username}")
    return jsonify({"ok": True})
