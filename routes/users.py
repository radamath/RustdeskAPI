"""Admin endpoints for RustDesk user management."""

from flask import Blueprint, jsonify, request

from models import RustdeskUser, UserToken, db
from routes.auth import admin_required, hash_password, log_audit

bp = Blueprint("users", __name__, url_prefix="/admin/api/users")


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
        "data": [{
            "id": u.id,
            "username": u.username,
            "email": u.email or "",
            "group_id": u.group_id,
            "group_name": u.group.name if u.group else None,
            "status": u.status,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "token_count": len(u.tokens),
        } for u in items],
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

    user = RustdeskUser(
        username=username,
        password_hash=hash_password(password),
        email=data.get("email", ""),
        group_id=data.get("group_id"),
        status=data.get("status", 1),
    )
    db.session.add(user)
    db.session.commit()
    log_audit("user_create", f"Kullanıcı oluşturuldu: {username}")
    return jsonify({"id": user.id}), 201


@bp.route("/<int:user_id>", methods=["GET"])
@admin_required
def get_user(user_id):
    u = db.session.get(RustdeskUser, user_id)
    if not u:
        return jsonify({"error": "Kullanıcı bulunamadı"}), 404
    return jsonify({
        "id": u.id,
        "username": u.username,
        "email": u.email or "",
        "group_id": u.group_id,
        "group_name": u.group.name if u.group else None,
        "status": u.status,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    })


@bp.route("/<int:user_id>", methods=["PUT"])
@admin_required
def update_user(user_id):
    u = db.session.get(RustdeskUser, user_id)
    if not u:
        return jsonify({"error": "Kullanıcı bulunamadı"}), 404

    data = request.get_json(silent=True) or {}
    if "email" in data:
        u.email = data["email"]
    if "group_id" in data:
        u.group_id = data["group_id"]
    if "status" in data:
        u.status = data["status"]
    if "password" in data and data["password"]:
        u.password_hash = hash_password(data["password"])

    db.session.commit()
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
    db.session.delete(u)
    db.session.commit()
    log_audit("user_delete", f"Kullanıcı silindi: {username}")
    return jsonify({"ok": True})
