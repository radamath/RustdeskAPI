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


def _is_valid_peer_id(pid):
    if not pid:
        return False
    return pid.isdigit() and len(pid) <= 15


def _enrich_peer(p, hb, tag, threshold):
    """Add heartbeat / tag data to a peer dict."""
    if hb:
        p["local_ip"] = hb.local_ip or ""
        p["global_ip"] = _clean_ip(hb.ip)
        p.setdefault("hostname", hb.hostname or "")
        p.setdefault("platform", hb.os_info or "")
        p["version"] = hb.version or ""
        try:
            ls = hb.last_seen.replace(tzinfo=None) if hb.last_seen and hb.last_seen.tzinfo else hb.last_seen
            p["online"] = ls >= threshold if ls else False
        except Exception:
            p["online"] = False
        p["last_seen"] = hb.last_seen.isoformat() if hb.last_seen else None
    else:
        p.setdefault("local_ip", "")
        p.setdefault("global_ip", "")
        p["online"] = False
        p.setdefault("last_seen", None)

    info = p.get("info", {})
    if not p.get("hostname") and info.get("hostname"):
        p["hostname"] = info["hostname"]
    if not p.get("platform") and info.get("os"):
        p["platform"] = info["os"]
    if not p.get("global_ip") and info.get("ip"):
        p["global_ip"] = _clean_ip(info["ip"])

    p["alias"] = tag.alias if tag else p.get("alias", "")
    p["tags"] = json.loads(tag.tags) if tag else p.get("tags", [])
    p["notes"] = tag.notes if tag else p.get("notes", "")
    p["group_id"] = tag.group_id if tag else p.get("group_id")

    p.setdefault("hostname", "")
    p.setdefault("platform", "")
    return p


@bp.route("", methods=["GET"])
@admin_required
def list_devices():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    search = request.args.get("search", "")

    rd_peers, _ = rustdesk_db.get_all_peers(search=search, page=1, per_page=999999)
    rd_ids = {p["id"] for p in rd_peers}

    all_heartbeats = Heartbeat.query.all()
    hb_map = {hb.id: hb for hb in all_heartbeats}

    hb_only_peers = []
    for hb in all_heartbeats:
        if hb.id not in rd_ids and _is_valid_peer_id(hb.id):
            if search and search.lower() not in hb.id.lower() and search.lower() not in (hb.hostname or "").lower():
                continue
            hb_only_peers.append({
                "id": hb.id,
                "uuid": "",
                "created_at": None,
                "user": "",
                "status": 0,
                "note": "",
                "info": {},
            })

    all_peers = rd_peers + hb_only_peers
    total = len(all_peers)

    start = (page - 1) * per_page
    page_peers = all_peers[start:start + per_page]

    all_ids = [p["id"] for p in page_peers]
    tags_map = {t.peer_id: t for t in PeerTag.query.filter(PeerTag.peer_id.in_(all_ids)).all()} if all_ids else {}

    now_naive = datetime.utcnow()
    threshold = now_naive - timedelta(minutes=5)

    result = []
    for p in page_peers:
        hb = hb_map.get(p["id"])
        tag = tags_map.get(p["id"])
        result.append(_enrich_peer(p, hb, tag, threshold))

    return jsonify({"data": result, "total": total, "page": page, "per_page": per_page})


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
