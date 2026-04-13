"""Admin endpoints for device/peer management."""

import json
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request

import rustdesk_db
from models import Heartbeat, PeerTag, db
from routes.auth import admin_required, log_audit

bp = Blueprint("devices", __name__, url_prefix="/admin/api/devices")


def _clean_ip(raw):
    """Strip IPv6-mapped prefix like ::ffff:1.2.3.4 → 1.2.3.4"""
    if not raw:
        return ""
    s = str(raw)
    if s.startswith("::ffff:"):
        return s[7:]
    return s


@bp.route("", methods=["GET"])
@admin_required
def list_devices():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    search = request.args.get("search", "")

    peers, total = rustdesk_db.get_all_peers(search=search, page=page, per_page=per_page)

    hb_ids = [p["id"] for p in peers]
    hb_map = {}
    if hb_ids:
        for hb in Heartbeat.query.filter(Heartbeat.id.in_(hb_ids)).all():
            hb_map[hb.id] = hb

    tags_map = {t.peer_id: t for t in PeerTag.query.filter(PeerTag.peer_id.in_(hb_ids)).all()} if hb_ids else {}

    now_naive = datetime.utcnow()
    threshold = now_naive - timedelta(minutes=5)

    for p in peers:
        hb = hb_map.get(p["id"])
        if hb:
            p["local_ip"] = hb.local_ip or ""
            p["global_ip"] = _clean_ip(hb.ip)
            p["hb_hostname"] = hb.hostname or ""
            p["os_info"] = hb.os_info or ""
            p["version"] = hb.version or ""
            try:
                ls = hb.last_seen.replace(tzinfo=None) if hb.last_seen and hb.last_seen.tzinfo else hb.last_seen
                p["online"] = ls >= threshold if ls else False
            except Exception:
                p["online"] = False
            p["last_seen"] = hb.last_seen.isoformat() if hb.last_seen else None
        else:
            p["local_ip"] = ""
            p["global_ip"] = _clean_ip(p.get("ip", "") or (p.get("info", {}).get("ip", "")))
            p["online"] = False
            p["last_seen"] = None
            p["hb_hostname"] = ""

        info = p.get("info", {})
        p["hostname"] = info.get("hostname", "") or p.get("hb_hostname", "")
        p["platform"] = info.get("os", "") or p.get("os_info", "")

        if not p["global_ip"] and info.get("ip"):
            p["global_ip"] = _clean_ip(info["ip"])

        tag = tags_map.get(p["id"])
        p["alias"] = tag.alias if tag else ""
        p["tags"] = json.loads(tag.tags) if tag else []
        p["notes"] = tag.notes if tag else ""
        p["group_id"] = tag.group_id if tag else None

        p.pop("hb_hostname", None)
        p.pop("os_info", None)

    return jsonify({"data": peers, "total": total, "page": page, "per_page": per_page})


@bp.route("/<peer_id>", methods=["GET"])
@admin_required
def get_device(peer_id):
    peer = rustdesk_db.get_peer(peer_id)
    if not peer:
        return jsonify({"error": "Cihaz bulunamadı"}), 404

    hb = db.session.get(Heartbeat, peer_id)
    if hb:
        peer["last_seen"] = hb.last_seen.isoformat() if hb.last_seen else None
        peer["local_ip"] = hb.local_ip or ""
        peer["global_ip"] = _clean_ip(hb.ip)
    else:
        peer["last_seen"] = None
        peer["local_ip"] = ""
        peer["global_ip"] = ""

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


@bp.route("/<peer_id>", methods=["DELETE"])
@admin_required
def delete_device(peer_id):
    Heartbeat.query.filter_by(id=peer_id).delete()
    PeerTag.query.filter_by(peer_id=peer_id).delete()
    db.session.commit()
    log_audit("device_delete", f"Cihaz silindi: {peer_id}")
    return jsonify({"ok": True})


@bp.route("/stats", methods=["GET"])
@admin_required
def device_stats():
    total = rustdesk_db.get_peer_count()
    now_naive = datetime.utcnow()
    threshold = now_naive - timedelta(minutes=5)
    online = Heartbeat.query.filter(Heartbeat.last_seen >= threshold).count()
    return jsonify({"total": total, "online": online, "offline": total - online})
