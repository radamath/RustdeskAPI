"""Admin endpoints for connection logs, file audits, and admin audit trail."""

from datetime import datetime

from flask import Blueprint, jsonify, request
from sqlalchemy import String, case, cast, func, or_

import rustdesk_db
from models import AuditLog, ConnectionLog, FileAudit, Heartbeat, PeerTag, db
from routes.auth import admin_required

bp = Blueprint("audit", __name__, url_prefix="/admin/api")


def _session_key_expr():
    """Tek oturum anahtarı: dolu conn_id gruplanır; boşsa her satır kendi başına."""
    return case(
        (
            or_(ConnectionLog.conn_id.is_(None), ConnectionLog.conn_id == ""),
            func.concat("row:", cast(ConnectionLog.id, String)),
        ),
        else_=ConnectionLog.conn_id,
    )


def _action_norm(action: str) -> str:
    return (action or "").strip().lower()


def _is_connect(action: str) -> bool:
    a = _action_norm(action)
    if a in ("disconnect",):
        return False
    return a in ("connect", "connection", "reconnect", "new")


def _is_close(action: str) -> bool:
    a = _action_norm(action)
    return a in ("close", "disconnect")


def _merge_session_rows(logs):
    """Aynı conn_id için connect / close satırlarını birleştirir (timestamp sıralı liste)."""
    if not logs:
        return None
    logs = sorted(logs, key=lambda x: (x.timestamp is None, x.timestamp or datetime.min))
    connect_row = None
    close_row = None
    for l in logs:
        if connect_row is None and _is_connect(l.action):
            connect_row = l
        if _is_close(l.action):
            close_row = l
    if connect_row is None:
        connect_row = logs[0]

    from_peer = connect_row.from_peer
    to_peer = connect_row.to_peer
    ip = (connect_row.ip or "").strip()
    started = connect_row.timestamp
    ended = close_row.timestamp if close_row else None

    if close_row and not ip:
        ip = (close_row.ip or "").strip()

    duration_sec = None
    if started and ended:
        duration_sec = (ended - started).total_seconds()
        if duration_sec < 0:
            duration_sec = None

    return {
        "from_peer": from_peer,
        "to_peer": to_peer,
        "connect_at": started.isoformat() if started else None,
        "close_at": ended.isoformat() if ended else None,
        "duration_sec": duration_sec,
        "ip": ip or "",
        "has_connect": any(_is_connect(l.action) for l in logs),
        "has_close": close_row is not None,
    }


def _peer_display_names(peer_ids: set):
    """RustDesk db_v2 hostname, yoksa Heartbeat hostname, yoksa PeerTag alias."""
    if not peer_ids:
        return {}
    tags = PeerTag.query.filter(PeerTag.peer_id.in_(peer_ids)).all()
    tag_map = {t.peer_id: (t.alias or "").strip() for t in tags}
    heartbeats = Heartbeat.query.filter(Heartbeat.id.in_(peer_ids)).all()
    hb_map = {h.id: (h.hostname or "").strip() for h in heartbeats if (h.hostname or "").strip()}
    out = {}
    for pid in peer_ids:
        name = ""
        p = rustdesk_db.get_peer(pid)
        if p:
            info = p.get("info") or {}
            name = (info.get("hostname") or "").strip()
        if not name:
            name = hb_map.get(pid) or ""
        if not name:
            name = tag_map.get(pid) or ""
        out[pid] = name
    return out


@bp.route("/connection-logs", methods=["GET"])
@admin_required
def connection_logs():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 30, type=int)
    search = request.args.get("search", "").strip()

    sk = _session_key_expr()

    subq = db.session.query(sk.label("sk")).select_from(ConnectionLog)
    if search:
        like = f"%{search}%"
        subq = subq.filter(
            (ConnectionLog.from_peer.ilike(like)) | (ConnectionLog.to_peer.ilike(like))
        )
    subq = subq.group_by(sk).subquery()

    total = db.session.query(func.count()).select_from(subq).scalar() or 0

    offset = (page - 1) * per_page
    sk_rows = (
        db.session.query(sk.label("sk"), func.max(ConnectionLog.timestamp).label("mt"))
        .select_from(ConnectionLog)
    )
    if search:
        like = f"%{search}%"
        sk_rows = sk_rows.filter(
            (ConnectionLog.from_peer.ilike(like)) | (ConnectionLog.to_peer.ilike(like))
        )
    sk_rows = (
        sk_rows.group_by(sk)
        .order_by(func.max(ConnectionLog.timestamp).desc())
        .offset(offset)
        .limit(per_page)
        .all()
    )

    data = []
    peer_ids = set()
    for row in sk_rows:
        session_key = row.sk
        if session_key.startswith("row:"):
            lid = int(session_key[4:])
            logs = ConnectionLog.query.filter_by(id=lid).all()
        else:
            logs = (
                ConnectionLog.query.filter_by(conn_id=session_key)
                .order_by(ConnectionLog.timestamp.asc())
                .all()
            )
        merged = _merge_session_rows(logs)
        if not merged:
            continue
        peer_ids.add(merged["from_peer"])
        peer_ids.add(merged["to_peer"])
        data.append(merged)

    names = _peer_display_names(peer_ids)
    for item in data:
        item["from_name"] = names.get(item["from_peer"], "")
        item["to_name"] = names.get(item["to_peer"], "")

    return jsonify({"data": data, "total": total})


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
