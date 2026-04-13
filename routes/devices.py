"""Admin endpoints for device/peer management."""

import json
from flask import Blueprint, jsonify, request

import rustdesk_db
from models import Heartbeat, PeerTag, db
from routes.auth import admin_required, log_audit

bp = Blueprint("devices", __name__, url_prefix="/admin/api/devices")


@bp.route("", methods=["GET"])
@admin_required
def list_devices():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    search = request.args.get("search", "")

    peers, total = rustdesk_db.get_all_peers(search=search, page=page, per_page=per_page)

    hb_ids = [p["id"] for p in peers]
    heartbeats = {h.id: h.last_seen.isoformat() for h in Heartbeat.query.filter(Heartbeat.id.in_(hb_ids)).all()} if hb_ids else {}

    tags_map = {t.peer_id: t for t in PeerTag.query.filter(PeerTag.peer_id.in_(hb_ids)).all()} if hb_ids else {}

    for p in peers:
        p["last_seen"] = heartbeats.get(p["id"])
        tag = tags_map.get(p["id"])
        p["alias"] = tag.alias if tag else ""
        p["tags"] = json.loads(tag.tags) if tag else []
        p["notes"] = tag.notes if tag else ""
        p["group_id"] = tag.group_id if tag else None

    return jsonify({"data": peers, "total": total, "page": page, "per_page": per_page})


@bp.route("/<peer_id>", methods=["GET"])
@admin_required
def get_device(peer_id):
    peer = rustdesk_db.get_peer(peer_id)
    if not peer:
        return jsonify({"error": "Cihaz bulunamadı"}), 404

    hb = db.session.get(Heartbeat, peer_id)
    peer["last_seen"] = hb.last_seen.isoformat() if hb else None

    tag = PeerTag.query.filter_by(peer_id=peer_id).first()
    peer["alias"] = tag.alias if tag else ""
    peer["tags"] = json.loads(tag.tags) if tag else []
    peer["notes"] = tag.notes if tag else ""
    peer["group_id"] = tag.group_id if tag else None

    return jsonify(peer)


@bp.route("/<peer_id>/tags", methods=["PUT"])
@admin_required
def update_device_tags(peer_id):
    data = request.get_json(silent=True) or {}
    tag = PeerTag.query.filter_by(peer_id=peer_id).first()
    if not tag:
        tag = PeerTag(peer_id=peer_id)
        db.session.add(tag)

    if "alias" in data:
        tag.alias = data["alias"]
    if "tags" in data:
        tag.tags = json.dumps(data["tags"])
    if "notes" in data:
        tag.notes = data["notes"]
    if "group_id" in data:
        tag.group_id = data["group_id"]

    db.session.commit()
    log_audit("device_update", f"Cihaz güncellendi: {peer_id}")
    return jsonify({"ok": True})


@bp.route("/stats", methods=["GET"])
@admin_required
def device_stats():
    from datetime import datetime, timedelta, timezone
    total = rustdesk_db.get_peer_count()
    threshold = datetime.now(timezone.utc) - timedelta(minutes=5)
    online = Heartbeat.query.filter(Heartbeat.last_seen >= threshold).count()
    return jsonify({"total": total, "online": online, "offline": total - online})
