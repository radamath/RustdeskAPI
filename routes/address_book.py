"""Admin endpoints for address book management."""

import json
from flask import Blueprint, jsonify, request

import rustdesk_db
from models import AddressBook, Heartbeat, RustdeskUser, db
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
    from datetime import datetime, timedelta, timezone

    ab = db.session.get(AddressBook, ab_id)
    if not ab:
        return jsonify({"error": "Adres defteri bulunamadı"}), 404

    peers = json.loads(ab.peers_json or "[]")
    peer_ids = [p.get("id") if isinstance(p, dict) else p for p in peers]

    hb_map = {}
    if peer_ids:
        for hb in Heartbeat.query.filter(Heartbeat.id.in_(peer_ids)).all():
            hb_map[hb.id] = hb

    rd_peer_map = {}
    for pid in peer_ids:
        rd = rustdesk_db.get_peer(pid)
        if rd:
            rd_peer_map[pid] = rd

    threshold = datetime.now(timezone.utc) - timedelta(minutes=5)
    enriched = []
    for p in peers:
        pid = p.get("id") if isinstance(p, dict) else p
        entry = dict(p) if isinstance(p, dict) else {"id": pid}

        hb = hb_map.get(pid)
        if hb:
            entry["ip"] = hb.ip or ""
            entry["online"] = hb.last_seen >= threshold if hb.last_seen else False
            entry["last_seen"] = hb.last_seen.isoformat() if hb.last_seen else None
        else:
            entry.setdefault("ip", "")
            entry["online"] = False
            entry["last_seen"] = None

        rd = rd_peer_map.get(pid)
        if rd:
            info = rd.get("info", {})
            if not entry.get("hostname") and info.get("hostname"):
                entry["hostname"] = info["hostname"]
            if not entry.get("platform") and info.get("os"):
                entry["platform"] = info["os"]

        entry.setdefault("hostname", "")
        entry.setdefault("platform", "")
        enriched.append(entry)

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
