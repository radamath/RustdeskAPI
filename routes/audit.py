"""Admin endpoints for connection logs, file audits, and admin audit trail."""

from datetime import datetime

from flask import Blueprint, jsonify, request
from sqlalchemy import String, and_, case, cast, func, or_

import rustdesk_db
from models import AuditLog, ConnectionLog, FileAudit, Heartbeat, PeerTag, db
from routes.auth import admin_required

bp = Blueprint("audit", __name__, url_prefix="/admin/api")


def _session_key_expr():
    """conn_id → session_id → tekil satır. conn_id yoksa sid: ile aynı oturum birleşir."""
    cid_set = and_(ConnectionLog.conn_id.isnot(None), ConnectionLog.conn_id != "")
    sid_set = and_(ConnectionLog.session_id.isnot(None), ConnectionLog.session_id != "")
    return case(
        (cid_set, ConnectionLog.conn_id),
        (sid_set, func.concat("sid:", ConnectionLog.session_id)),
        else_=func.concat("row:", cast(ConnectionLog.id, String)),
    )


def _action_norm(action: str) -> str:
    return (action or "").strip().lower()


def _is_session_start(action: str) -> bool:
    """Başlangıç zamanı için (new dahil — ayrı satır üretilmez)."""
    a = _action_norm(action)
    if a in ("disconnect",):
        return False
    return a in ("connect", "connection", "reconnect", "new")


def _is_connect(action: str) -> bool:
    """Rozet 'Bağlandı' için: new hariç klasik connect (new sadece sürede kullanılır)."""
    a = _action_norm(action)
    return a in ("connect", "connection", "reconnect")


def _is_close(action: str) -> bool:
    a = _action_norm(action)
    return a in ("close", "disconnect")


def _merge_session_rows(logs):
    """Tek oturum satırı; close’ta eksik kalan hedef/kaynak diğer satırlardan tamamlanır."""
    if not logs:
        return None
    logs = sorted(logs, key=lambda x: (x.timestamp is None, x.timestamp or datetime.min))

    close_row = None
    for l in logs:
        if _is_close(l.action):
            close_row = l

    from_peer, to_peer = "", ""
    for l in logs:
        a, b = (l.from_peer or "").strip(), (l.to_peer or "").strip()
        if a and b:
            from_peer, to_peer = a, b
            break
    if not from_peer or not to_peer:
        seen = []
        sset = set()
        for l in logs:
            for p in ((l.from_peer or "").strip(), (l.to_peer or "").strip()):
                if p and p not in sset:
                    sset.add(p)
                    seen.append(p)
        if len(seen) >= 2:
            if not from_peer:
                from_peer = seen[0]
            if not to_peer:
                for p in seen:
                    if p != from_peer:
                        to_peer = p
                        break
        elif len(seen) == 1:
            if not from_peer:
                from_peer = seen[0]
            elif not to_peer:
                to_peer = seen[0]

    start_ts = None
    start_row_for_ip = None
    for l in logs:
        if _is_session_start(l.action) and l.timestamp:
            if start_ts is None or l.timestamp < start_ts:
                start_ts = l.timestamp
                start_row_for_ip = l
    if start_ts is None:
        start_ts = logs[0].timestamp
        start_row_for_ip = logs[0]

    ended = close_row.timestamp if close_row else None
    ip = ""
    if start_row_for_ip:
        ip = (start_row_for_ip.ip or "").strip()
    if close_row and not ip:
        ip = (close_row.ip or "").strip()

    duration_sec = None
    if start_ts and ended:
        duration_sec = (ended - start_ts).total_seconds()
        if duration_sec < 0:
            duration_sec = None

    has_real_connect = any(_is_connect(l.action) for l in logs)
    has_start = any(_is_session_start(l.action) for l in logs)

    return {
        "from_peer": from_peer or "",
        "to_peer": to_peer or "",
        "connect_at": start_ts.isoformat() if start_ts else None,
        "close_at": ended.isoformat() if ended else None,
        "duration_sec": duration_sec,
        "ip": ip or "",
        "has_connect": has_real_connect or has_start,
        "has_close": close_row is not None,
    }


def _peer_id_variants(pid: str) -> list:
    s = (pid or "").strip()
    if not s:
        return []
    out = [s]
    if s.isdigit():
        n = str(int(s))
        if n != s:
            out.append(n)
    return out


def _peer_display_names(peer_ids: set):
    """RustDesk db_v2 hostname, yoksa Heartbeat, yoksa PeerTag. ID baştaki 0 farkını tolere eder."""
    if not peer_ids:
        return {}
    all_cands = set()
    variants = {pid: _peer_id_variants(pid) for pid in peer_ids}
    for vlist in variants.values():
        all_cands.update(vlist)
    all_cands.discard("")
    tags = PeerTag.query.filter(PeerTag.peer_id.in_(list(all_cands))).all() if all_cands else []
    tag_map = {t.peer_id: (t.alias or "").strip() for t in tags}
    heartbeats = Heartbeat.query.filter(Heartbeat.id.in_(list(all_cands))).all() if all_cands else []
    hb_map = {h.id: (h.hostname or "").strip() for h in heartbeats if (h.hostname or "").strip()}
    out = {}
    for pid in peer_ids:
        name = ""
        for cand in variants.get(pid, [pid]):
            if not cand:
                continue
            p = rustdesk_db.get_peer(cand)
            if p:
                info = p.get("info") or {}
                name = (info.get("hostname") or "").strip()
                if name:
                    break
            if not name:
                hn = hb_map.get(cand, "")
                if hn:
                    name = hn
                    break
            if not name:
                al = tag_map.get(cand, "")
                if al:
                    name = al
                    break
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
        elif session_key.startswith("sid:"):
            sid = session_key[4:]
            logs = (
                ConnectionLog.query.filter_by(session_id=sid)
                .order_by(ConnectionLog.timestamp.asc())
                .all()
            )
        else:
            logs = (
                ConnectionLog.query.filter_by(conn_id=session_key)
                .order_by(ConnectionLog.timestamp.asc())
                .all()
            )
        merged = _merge_session_rows(logs)
        if not merged:
            continue
        for k in ("from_peer", "to_peer"):
            v = (merged.get(k) or "").strip()
            if v:
                peer_ids.add(v)
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
