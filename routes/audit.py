"""Admin endpoints for connection logs, file audits, and admin audit trail."""

from flask import Blueprint, jsonify, request

from models import AuditLog, ConnectionLog, FileAudit
from routes.auth import admin_required

bp = Blueprint("audit", __name__, url_prefix="/admin/api")


@bp.route("/connection-logs", methods=["GET"])
@admin_required
def connection_logs():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 30, type=int)
    search = request.args.get("search", "")

    q = ConnectionLog.query
    if search:
        q = q.filter(
            (ConnectionLog.from_peer.ilike(f"%{search}%")) |
            (ConnectionLog.to_peer.ilike(f"%{search}%"))
        )
    total = q.count()
    items = q.order_by(ConnectionLog.timestamp.desc()).offset((page - 1) * per_page).limit(per_page).all()

    return jsonify({
        "data": [{
            "id": l.id,
            "conn_id": l.conn_id,
            "from_peer": l.from_peer,
            "to_peer": l.to_peer,
            "action": l.action,
            "ip": l.ip,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
        } for l in items],
        "total": total,
    })


@bp.route("/file-audits", methods=["GET"])
@admin_required
def file_audits():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 30, type=int)

    q = FileAudit.query.order_by(FileAudit.timestamp.desc())
    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()

    return jsonify({
        "data": [{
            "id": f.id,
            "conn_id": f.conn_id,
            "peer_id": f.peer_id,
            "path": f.path,
            "action": f.action,
            "timestamp": f.timestamp.isoformat() if f.timestamp else None,
        } for f in items],
        "total": total,
    })


@bp.route("/audit-logs", methods=["GET"])
@admin_required
def audit_logs():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 30, type=int)

    q = AuditLog.query.order_by(AuditLog.timestamp.desc())
    total = q.count()
    items = q.offset((page - 1) * per_page).limit(per_page).all()

    return jsonify({
        "data": [{
            "id": a.id,
            "admin_user_id": a.admin_user_id,
            "action": a.action,
            "details": a.details,
            "ip_address": a.ip_address,
            "timestamp": a.timestamp.isoformat() if a.timestamp else None,
        } for a in items],
        "total": total,
    })
