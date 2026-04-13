"""Admin endpoints for server settings and API key management."""

import hashlib
import os
import secrets

from flask import Blueprint, jsonify, request

from models import ApiKey, Setting, db
from routes.auth import admin_required, log_audit

bp = Blueprint("settings", __name__, url_prefix="/admin/api")


# ── Settings ────────────────────────────────────────────────────────

@bp.route("/settings", methods=["GET"])
@admin_required
def list_settings():
    items = Setting.query.order_by(Setting.key).all()
    return jsonify({
        "data": [{
            "key": s.key,
            "value": s.value,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        } for s in items]
    })


@bp.route("/settings", methods=["PUT"])
@admin_required
def update_settings():
    data = request.get_json(silent=True) or {}
    for key, value in data.items():
        s = db.session.get(Setting, key)
        if s:
            s.value = str(value)
        else:
            s = Setting(key=key, value=str(value))
            db.session.add(s)
    db.session.commit()
    log_audit("settings_update", f"Ayarlar güncellendi: {list(data.keys())}")
    return jsonify({"ok": True})


@bp.route("/settings/<key>", methods=["DELETE"])
@admin_required
def delete_setting(key):
    s = db.session.get(Setting, key)
    if s:
        db.session.delete(s)
        db.session.commit()
        log_audit("settings_delete", f"Ayar silindi: {key}")
    return jsonify({"ok": True})


# ── Server info (reads RustDesk key files) ──────────────────────────

@bp.route("/server-info", methods=["GET"])
@admin_required
def server_info():
    from flask import current_app
    rd_db_path = current_app.config["RUSTDESK_DB_PATH"]
    rd_dir = os.path.dirname(rd_db_path) if rd_db_path else ""

    pub_key = ""
    key_path = os.path.join(rd_dir, "id_ed25519.pub") if rd_dir else ""
    if key_path and os.path.isfile(key_path):
        with open(key_path, "r") as f:
            pub_key = f.read().strip()

    return jsonify({
        "public_key": pub_key,
        "rustdesk_db_path": rd_db_path,
        "rustdesk_db_exists": os.path.isfile(rd_db_path) if rd_db_path else False,
    })


# ── API Keys ────────────────────────────────────────────────────────

@bp.route("/api-keys", methods=["GET"])
@admin_required
def list_api_keys():
    items = ApiKey.query.order_by(ApiKey.created_at.desc()).all()
    return jsonify({
        "data": [{
            "id": k.id,
            "name": k.name,
            "key_prefix": k.key_prefix,
            "is_active": k.is_active,
            "created_at": k.created_at.isoformat() if k.created_at else None,
            "last_used": k.last_used.isoformat() if k.last_used else None,
        } for k in items]
    })


@bp.route("/api-keys", methods=["POST"])
@admin_required
def create_api_key():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "API anahtarı adı gerekli"}), 400

    raw_key = secrets.token_urlsafe(32)
    prefix = raw_key[:8]
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    k = ApiKey(
        name=name,
        key_hash=key_hash,
        key_prefix=prefix,
        created_by=request._admin_user.id,
    )
    db.session.add(k)
    db.session.commit()
    log_audit("apikey_create", f"API anahtarı oluşturuldu: {name}")
    return jsonify({"id": k.id, "key": raw_key}), 201


@bp.route("/api-keys/<int:key_id>", methods=["DELETE"])
@admin_required
def delete_api_key(key_id):
    k = db.session.get(ApiKey, key_id)
    if not k:
        return jsonify({"error": "API anahtarı bulunamadı"}), 404
    name = k.name
    db.session.delete(k)
    db.session.commit()
    log_audit("apikey_delete", f"API anahtarı silindi: {name}")
    return jsonify({"ok": True})


@bp.route("/api-keys/<int:key_id>/toggle", methods=["POST"])
@admin_required
def toggle_api_key(key_id):
    k = db.session.get(ApiKey, key_id)
    if not k:
        return jsonify({"error": "API anahtarı bulunamadı"}), 404
    k.is_active = not k.is_active
    db.session.commit()
    state = "etkinleştirildi" if k.is_active else "devre dışı bırakıldı"
    log_audit("apikey_toggle", f"API anahtarı {state}: {k.name}")
    return jsonify({"ok": True, "is_active": k.is_active})


# ── Dashboard stats ─────────────────────────────────────────────────

@bp.route("/dashboard", methods=["GET"])
@admin_required
def dashboard():
    from datetime import datetime, timedelta, timezone
    import rustdesk_db
    from models import ConnectionLog, Heartbeat, RustdeskUser

    now = datetime.now(timezone.utc)
    total_peers = rustdesk_db.get_peer_count()
    online_threshold = now - timedelta(minutes=5)
    online_peers = Heartbeat.query.filter(Heartbeat.last_seen >= online_threshold).count()
    total_users = RustdeskUser.query.count()
    total_connections = ConnectionLog.query.count()

    week_ago = now - timedelta(days=7)
    recent_logs = (
        ConnectionLog.query
        .filter(ConnectionLog.timestamp >= week_ago)
        .order_by(ConnectionLog.timestamp.desc())
        .limit(10)
        .all()
    )

    daily_counts = {}
    for i in range(7):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        daily_counts[day] = 0
    day_logs = (
        ConnectionLog.query
        .filter(ConnectionLog.timestamp >= week_ago)
        .all()
    )
    for log in day_logs:
        if log.timestamp:
            day_key = log.timestamp.strftime("%Y-%m-%d")
            if day_key in daily_counts:
                daily_counts[day_key] += 1

    return jsonify({
        "total_peers": total_peers,
        "online_peers": online_peers,
        "total_users": total_users,
        "total_connections": total_connections,
        "recent_connections": [{
            "id": l.id,
            "from_peer": l.from_peer,
            "to_peer": l.to_peer,
            "action": l.action,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
        } for l in recent_logs],
        "daily_connections": daily_counts,
    })
