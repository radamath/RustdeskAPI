"""RustDesk client-compatible API endpoints.

These endpoints mimic the official RustDesk API so that clients configured
with  api-server = http://<host>:21114  work out of the box.
"""

import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from models import (
    AddressBook, ConnectionLog, FileAudit, Heartbeat, RustdeskUser,
    UserToken, db,
)
from routes.auth import (
    check_password, create_client_jwt, decode_client_jwt, hash_password,
)

bp = Blueprint("api", __name__, url_prefix="/api")


def _get_current_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    payload = decode_client_jwt(auth[7:])
    if not payload:
        return None
    return db.session.get(RustdeskUser, payload["user_id"])


# ── Basic info ──────────────────────────────────────────────────────

@bp.route("/", methods=["GET"])
def index():
    return jsonify({"data": "RustDesk API Server"})


@bp.route("/version", methods=["GET"])
def version():
    return jsonify({"data": "1.0.0"})


# ── Auth ────────────────────────────────────────────────────────────

@bp.route("/login-options", methods=["GET"])
def login_options():
    return jsonify(["common-oidc/[password]"])


@bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    device_id = data.get("id", "")
    device_info = json.dumps(data.get("deviceInfo", {}))

    user = RustdeskUser.query.filter_by(username=username).first()
    if not user or not check_password(password, user.password_hash):
        return jsonify({"error": "Invalid credentials"}), 401
    if user.status != 1:
        return jsonify({"error": "Account disabled"}), 403

    token_str = create_client_jwt(user.id, user.username)

    tok = UserToken(
        user_id=user.id,
        token=token_str,
        device_id=device_id,
        device_info=device_info,
    )
    db.session.add(tok)
    db.session.commit()

    return jsonify({
        "type": "access_token",
        "access_token": token_str,
        "user": {
            "name": user.username,
            "email": user.email or "",
            "status": user.status,
        },
    })


@bp.route("/logout", methods=["POST"])
def logout():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        UserToken.query.filter_by(token=auth[7:]).delete()
        db.session.commit()
    return jsonify({})


# ── Heartbeat ───────────────────────────────────────────────────────

@bp.route("/heartbeat", methods=["POST"])
def heartbeat():
    data = request.get_json(silent=True) or {}
    uid = data.get("uuid", "") or data.get("id", "")
    if uid:
        now = datetime.now(timezone.utc)
        hb = db.session.get(Heartbeat, uid)
        if hb:
            if (now - hb.last_seen).total_seconds() > 30:
                hb.last_seen = now
        else:
            hb = Heartbeat(id=uid, uuid=uid, last_seen=now)
            db.session.add(hb)
        db.session.commit()
    return jsonify({})


# ── Sysinfo ─────────────────────────────────────────────────────────

@bp.route("/sysinfo", methods=["POST"])
def sysinfo():
    return jsonify({"data": "SYSINFO_UPDATED"})


@bp.route("/sysinfo_ver", methods=["POST"])
def sysinfo_ver():
    return jsonify({"data": "1.0.0"})


# ── Current user ────────────────────────────────────────────────────

@bp.route("/currentUser", methods=["GET"])
@bp.route("/user/info", methods=["GET"])
def current_user():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({
        "name": user.username,
        "email": user.email or "",
        "status": user.status,
    })


# ── Peers ───────────────────────────────────────────────────────────

@bp.route("/peers", methods=["GET"])
def peers():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    import rustdesk_db
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("pageSize", 50, type=int)
    items, total = rustdesk_db.get_all_peers(page=page, per_page=page_size)
    return jsonify({"data": items, "total": total})


# ── Users list (for client) ────────────────────────────────────────

@bp.route("/users", methods=["GET"])
def users_list():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("pageSize", 50, type=int)
    q = RustdeskUser.query.filter_by(status=1)
    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return jsonify({
        "data": [{"name": u.username, "email": u.email or ""} for u in items],
        "total": total,
    })


# ── Address Book ────────────────────────────────────────────────────

@bp.route("/ab", methods=["GET"])
def ab_get():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    book = AddressBook.query.filter_by(user_id=user.id, name="default").first()
    if not book:
        return jsonify({"data": {"peers": [], "tags": []}})
    return jsonify({
        "data": {
            "peers": json.loads(book.peers_json or "[]"),
            "tags": json.loads(book.tags_json or "[]"),
        }
    })


@bp.route("/ab", methods=["POST"])
def ab_update():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    ab_data = data.get("data", data)

    book = AddressBook.query.filter_by(user_id=user.id, name="default").first()
    if not book:
        book = AddressBook(user_id=user.id, name="default")
        db.session.add(book)

    if "peers" in ab_data:
        book.peers_json = json.dumps(ab_data["peers"])
    if "tags" in ab_data:
        book.tags_json = json.dumps(ab_data["tags"])
    db.session.commit()
    return jsonify({})


@bp.route("/ab/personal", methods=["POST"])
def ab_personal():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    book = AddressBook.query.filter_by(user_id=user.id, name="default").first()
    if not book:
        return jsonify({"data": {"peers": [], "tags": [], "guid": ""}})
    return jsonify({
        "data": {
            "guid": book.guid,
            "peers": json.loads(book.peers_json or "[]"),
            "tags": json.loads(book.tags_json or "[]"),
        }
    })


@bp.route("/ab/settings", methods=["POST"])
def ab_settings():
    return jsonify({"data": {}})


@bp.route("/ab/shared/profiles", methods=["POST"])
def ab_shared_profiles():
    return jsonify({"data": [], "total": 0})


@bp.route("/ab/peers", methods=["POST"])
def ab_peers():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    book = AddressBook.query.filter_by(user_id=user.id, name="default").first()
    if not book:
        return jsonify({"data": [], "total": 0})
    peers = json.loads(book.peers_json or "[]")
    return jsonify({"data": peers, "total": len(peers)})


# ── Audit ───────────────────────────────────────────────────────────

@bp.route("/audit/conn", methods=["POST"])
def audit_conn():
    data = request.get_json(silent=True) or {}
    log = ConnectionLog(
        conn_id=str(data.get("conn_id", "")),
        from_peer=data.get("from", data.get("from_peer", "")),
        to_peer=data.get("to", data.get("to_peer", "")),
        action=data.get("action", "connect"),
        ip=data.get("ip", request.remote_addr or ""),
        session_id=str(data.get("session_id", "")),
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({})


@bp.route("/audit/file", methods=["POST"])
def audit_file():
    data = request.get_json(silent=True) or {}
    entry = FileAudit(
        conn_id=str(data.get("conn_id", "")),
        peer_id=data.get("peer_id", ""),
        path=data.get("path", ""),
        action=data.get("action", ""),
        info=json.dumps(data.get("info", {})),
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify({})


# ── Server config (for web client) ─────────────────────────────────

@bp.route("/server-config", methods=["POST"])
def server_config():
    return jsonify({"data": {}})


@bp.route("/server-config-v2", methods=["POST"])
def server_config_v2():
    return jsonify({"data": {}})
