"""Admin endpoints for RustDesk user management."""

import json

from flask import Blueprint, jsonify, request

import rustdesk_db
from models import AddressBook, Heartbeat, PeerTag, RustdeskUser, UserToken, db
from routes.auth import admin_required, hash_password, log_audit

bp = Blueprint("users", __name__, url_prefix="/admin/api/users")


# ── Sync helper ──────────────────────────────────────────────────────

def _is_valid_peer_id(pid):
    """RustDesk peer IDs are short numeric strings (e.g. '190794556').
    Base64 UUIDs and other internal IDs should be excluded."""
    if not pid:
        return False
    return pid.isdigit() and len(pid) <= 15


def sync_admin_address_books(exclude_peer_id=None):
    """Ensure every admin-role RustdeskUser has all system peers in their
    default address book.  Called on heartbeat (new peer) and role change."""
    all_peers_raw, _ = rustdesk_db.get_all_peers(page=1, per_page=999999)

    heartbeats = {h.id: h for h in Heartbeat.query.all()}
    alias_map = {t.peer_id: t.alias for t in PeerTag.query.filter(PeerTag.alias != "").all()}

    system_peers = []
    for rp in all_peers_raw:
        if not _is_valid_peer_id(rp["id"]):
            continue
        info = rp.get("info", {})
        entry = {
            "id": rp["id"],
            "hostname": info.get("hostname", ""),
            "platform": info.get("os", ""),
            "alias": alias_map.get(rp["id"], ""),
            "tags": [],
        }
        hb = heartbeats.get(rp["id"])
        if hb and hb.ip:
            entry["ip"] = hb.ip
        system_peers.append(entry)

    for hb_id, hb in heartbeats.items():
        if not _is_valid_peer_id(hb_id):
            continue
        if not any(p["id"] == hb_id for p in system_peers):
            system_peers.append({
                "id": hb_id,
                "hostname": "",
                "platform": "",
                "alias": alias_map.get(hb_id, ""),
                "tags": [],
                "ip": hb.ip or "",
            })

    admins = RustdeskUser.query.filter_by(role="admin", status=1).all()
    for admin in admins:
        book = AddressBook.query.filter_by(user_id=admin.id, name="default").first()
        if not book:
            book = AddressBook(user_id=admin.id, name="default")
            db.session.add(book)
            db.session.flush()

        existing = json.loads(book.peers_json or "[]")

        cleaned = [
            p for p in existing
            if _is_valid_peer_id(p.get("id") if isinstance(p, dict) else p)
        ]

        existing_ids = {
            (p.get("id") if isinstance(p, dict) else p) for p in cleaned
        }

        for p in cleaned:
            if isinstance(p, dict) and p.get("id") in alias_map:
                p["alias"] = alias_map[p["id"]]

        merged = list(cleaned)
        for sp in system_peers:
            if sp["id"] not in existing_ids:
                merged.append(sp)

        book.peers_json = json.dumps(merged)

    db.session.commit()


# ── CRUD ─────────────────────────────────────────────────────────────

def _user_dict(u):
    ab = AddressBook.query.filter_by(user_id=u.id, name="default").first()
    return {
        "id": u.id,
        "username": u.username,
        "email": u.email or "",
        "role": u.role or "user",
        "group_id": u.group_id,
        "group_name": u.group.name if u.group else None,
        "status": u.status,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "token_count": len(u.tokens),
        "ab_peer_count": len(json.loads(ab.peers_json or "[]")) if ab else 0,
    }


@bp.route("", methods=["GET"])
@admin_required
def list_users():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    search = request.args.get("search", "")

    q = RustdeskUser.query
    if search:
        q = q.filter(RustdeskUser.username.ilike(f"%{search}%"))
    total = q.count()
    items = q.order_by(RustdeskUser.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()

    return jsonify({
        "data": [_user_dict(u) for u in items],
        "total": total,
        "page": page,
        "per_page": per_page,
    })


@bp.route("", methods=["POST"])
@admin_required
def create_user():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not username or not password:
        return jsonify({"error": "Kullanıcı adı ve şifre gerekli"}), 400

    if RustdeskUser.query.filter_by(username=username).first():
        return jsonify({"error": "Bu kullanıcı adı zaten mevcut"}), 409

    role = data.get("role", "user")
    if role not in ("admin", "user"):
        role = "user"

    user = RustdeskUser(
        username=username,
        password_hash=hash_password(password),
        email=data.get("email", ""),
        role=role,
        group_id=data.get("group_id"),
        status=data.get("status", 1),
    )
    db.session.add(user)
    db.session.commit()

    if role == "admin":
        sync_admin_address_books()

    log_audit("user_create", f"Kullanıcı oluşturuldu: {username} (rol: {role})")
    return jsonify({"id": user.id}), 201


@bp.route("/<int:user_id>", methods=["GET"])
@admin_required
def get_user(user_id):
    u = db.session.get(RustdeskUser, user_id)
    if not u:
        return jsonify({"error": "Kullanıcı bulunamadı"}), 404
    return jsonify(_user_dict(u))


@bp.route("/<int:user_id>", methods=["PUT"])
@admin_required
def update_user(user_id):
    u = db.session.get(RustdeskUser, user_id)
    if not u:
        return jsonify({"error": "Kullanıcı bulunamadı"}), 404

    data = request.get_json(silent=True) or {}
    old_role = u.role or "user"

    if "email" in data:
        u.email = data["email"]
    if "group_id" in data:
        u.group_id = data["group_id"]
    if "status" in data:
        u.status = data["status"]
    if "password" in data and data["password"]:
        u.password_hash = hash_password(data["password"])
    if "role" in data and data["role"] in ("admin", "user"):
        u.role = data["role"]

    db.session.commit()

    if u.role == "admin" and old_role != "admin":
        sync_admin_address_books()

    log_audit("user_update", f"Kullanıcı güncellendi: {u.username}")
    return jsonify({"ok": True})


@bp.route("/<int:user_id>", methods=["DELETE"])
@admin_required
def delete_user(user_id):
    u = db.session.get(RustdeskUser, user_id)
    if not u:
        return jsonify({"error": "Kullanıcı bulunamadı"}), 404
    username = u.username
    UserToken.query.filter_by(user_id=user_id).delete()
    AddressBook.query.filter_by(user_id=user_id).delete()
    db.session.delete(u)
    db.session.commit()
    log_audit("user_delete", f"Kullanıcı silindi: {username}")
    return jsonify({"ok": True})


# ── User address book detail (for admin panel) ──────────────────────

@bp.route("/<int:user_id>/address-book", methods=["GET"])
@admin_required
def user_address_book(user_id):
    from routes.peer_enrichment import enrich_peers

    u = db.session.get(RustdeskUser, user_id)
    if not u:
        return jsonify({"error": "Kullanıcı bulunamadı"}), 404

    book = AddressBook.query.filter_by(user_id=u.id, name="default").first()
    if not book:
        return jsonify({"peers": [], "tags": []})

    enriched = enrich_peers(book.peers_json)
    return jsonify({
        "peers": enriched,
        "tags": json.loads(book.tags_json or "[]"),
    })
