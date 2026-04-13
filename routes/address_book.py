"""Admin endpoints for address book management."""

import json
from flask import Blueprint, jsonify, request

from models import AddressBook, db
from routes.auth import admin_required, log_audit

bp = Blueprint("address_book", __name__, url_prefix="/admin/api/address-books")


@bp.route("", methods=["GET"])
@admin_required
def list_address_books():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)

    q = AddressBook.query.order_by(AddressBook.updated_at.desc())
    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()

    return jsonify({
        "data": [{
            "id": ab.id,
            "guid": ab.guid,
            "name": ab.name,
            "user_id": ab.user_id,
            "username": ab.user.username if ab.user else "?",
            "peer_count": len(json.loads(ab.peers_json or "[]")),
            "tag_count": len(json.loads(ab.tags_json or "[]")),
            "updated_at": ab.updated_at.isoformat() if ab.updated_at else None,
        } for ab in items],
        "total": total,
    })


@bp.route("/<int:ab_id>", methods=["GET"])
@admin_required
def get_address_book(ab_id):
    from routes.peer_enrichment import enrich_peers

    ab = db.session.get(AddressBook, ab_id)
    if not ab:
        return jsonify({"error": "Adres defteri bulunamadı"}), 404

    enriched = enrich_peers(ab.peers_json)

    return jsonify({
        "id": ab.id,
        "guid": ab.guid,
        "name": ab.name,
        "user_id": ab.user_id,
        "username": ab.user.username if ab.user else "?",
        "peers": enriched,
        "tags": json.loads(ab.tags_json or "[]"),
        "updated_at": ab.updated_at.isoformat() if ab.updated_at else None,
    })


@bp.route("/<int:ab_id>", methods=["PUT"])
@admin_required
def update_address_book(ab_id):
    ab = db.session.get(AddressBook, ab_id)
    if not ab:
        return jsonify({"error": "Adres defteri bulunamadı"}), 404
    data = request.get_json(silent=True) or {}
    if "peers" in data:
        ab.peers_json = json.dumps(data["peers"])
    if "tags" in data:
        ab.tags_json = json.dumps(data["tags"])
    if "name" in data:
        ab.name = data["name"]
    db.session.commit()
    log_audit("addressbook_update", f"Adres defteri güncellendi: {ab.guid}")
    return jsonify({"ok": True})


@bp.route("/<int:ab_id>", methods=["DELETE"])
@admin_required
def delete_address_book(ab_id):
    ab = db.session.get(AddressBook, ab_id)
    if not ab:
        return jsonify({"error": "Adres defteri bulunamadı"}), 404
    guid = ab.guid
    db.session.delete(ab)
    db.session.commit()
    log_audit("addressbook_delete", f"Adres defteri silindi: {guid}")
    return jsonify({"ok": True})
