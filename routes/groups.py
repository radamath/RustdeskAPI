"""Admin endpoints for device/user group management."""

from flask import Blueprint, jsonify, request

from models import DeviceGroup, db
from routes.auth import admin_required, log_audit

bp = Blueprint("groups", __name__, url_prefix="/admin/api/groups")


@bp.route("", methods=["GET"])
@admin_required
def list_groups():
    groups = DeviceGroup.query.order_by(DeviceGroup.name).all()
    return jsonify({
        "data": [{
            "id": g.id,
            "name": g.name,
            "description": g.description or "",
            "user_count": len(g.users),
            "peer_count": len(g.peers),
            "created_at": g.created_at.isoformat() if g.created_at else None,
        } for g in groups]
    })


@bp.route("", methods=["POST"])
@admin_required
def create_group():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Grup adı gerekli"}), 400
    if DeviceGroup.query.filter_by(name=name).first():
        return jsonify({"error": "Bu grup adı zaten mevcut"}), 409

    g = DeviceGroup(name=name, description=data.get("description", ""))
    db.session.add(g)
    db.session.commit()
    log_audit("group_create", f"Grup oluşturuldu: {name}")
    return jsonify({"id": g.id}), 201


@bp.route("/<int:group_id>", methods=["PUT"])
@admin_required
def update_group(group_id):
    g = db.session.get(DeviceGroup, group_id)
    if not g:
        return jsonify({"error": "Grup bulunamadı"}), 404
    data = request.get_json(silent=True) or {}
    if "name" in data:
        g.name = data["name"]
    if "description" in data:
        g.description = data["description"]
    db.session.commit()
    log_audit("group_update", f"Grup güncellendi: {g.name}")
    return jsonify({"ok": True})


@bp.route("/<int:group_id>", methods=["DELETE"])
@admin_required
def delete_group(group_id):
    g = db.session.get(DeviceGroup, group_id)
    if not g:
        return jsonify({"error": "Grup bulunamadı"}), 404
    name = g.name
    db.session.delete(g)
    db.session.commit()
    log_audit("group_delete", f"Grup silindi: {name}")
    return jsonify({"ok": True})
