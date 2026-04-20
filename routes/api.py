"""RustDesk client-compatible API endpoints.

These endpoints mimic the official RustDesk API so that clients configured
with  api-server = http://<host>:21114  work out of the box.
"""

import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from config import Config

from models import (
    AddressBook, ConnectionLog, FileAudit, Heartbeat, PeerTag,
    RustdeskUser, UserToken, db,
)
from routes.auth import (
    check_password, create_client_jwt, decode_client_jwt, hash_password,
)

bp = Blueprint("api", __name__, url_prefix="/api")


def _backfill_audit_endpoints(fp: str, tp: str, conn_id: str, session_id: str) -> tuple[str, str]:
    """RustDesk bazen close/new satırında karşı peer göndermez; aynı oturumdan tamamla."""
    fp = (fp or "").strip()
    tp = (tp or "").strip()
    if fp and tp:
        return fp, tp
    rows = []
    cid = (conn_id or "").strip()
    sid = (session_id or "").strip()
    if cid:
        rows = (
            ConnectionLog.query.filter_by(conn_id=cid)
            .order_by(ConnectionLog.timestamp.asc())
            .limit(80)
            .all()
        )
    if not rows and sid:
        rows = (
            ConnectionLog.query.filter_by(session_id=sid)
            .order_by(ConnectionLog.timestamp.asc())
            .limit(80)
            .all()
        )
    seen = []
    sset = set()
    for r in rows:
        for p in ((r.from_peer or "").strip(), (r.to_peer or "").strip()):
            if p and p not in sset:
                sset.add(p)
                seen.append(p)
    if len(seen) >= 2:
        if not fp:
            fp = seen[0]
        if not tp:
            for p in seen:
                if p != fp:
                    tp = p
                    break
    elif len(seen) == 1:
        if not fp:
            fp = seen[0]
        elif not tp:
            tp = seen[0]
    return fp, tp


def _inject_server_aliases(peers):
    """Overlay PeerTag aliases onto address-book peers so the RustDesk
    client always sees admin-set names, even after a client push."""
    if not peers:
        return peers
    peer_ids = [p.get("id") for p in peers if isinstance(p, dict) and p.get("id")]
    if not peer_ids:
        return peers
    alias_map = {
        t.peer_id: t.alias
        for t in PeerTag.query.filter(PeerTag.peer_id.in_(peer_ids), PeerTag.alias != "").all()
    }
    if not alias_map:
        return peers
    for p in peers:
        if isinstance(p, dict) and p.get("id") in alias_map:
            p["alias"] = alias_map[p["id"]]
    return peers


def _get_current_user():
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    payload = decode_client_jwt(auth[7:])
    if not payload:
        return None
    return db.session.get(RustdeskUser, payload["user_id"])


# ── Basic info ──────────────────────────────────────────────────────

@bp.route("/", methods=["GET"])
def index():
    return jsonify({"data": "RustDesk API Server"})


@bp.route("/version", methods=["GET"])
def version():
    return jsonify({"data": "1.0.0"})


# ── Auth ────────────────────────────────────────────────────────────

@bp.route("/login-options", methods=["GET"])
def login_options():
    return jsonify(["common-oidc/[password]"])


@bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    password = data.get("password", "")
    device_id = data.get("id", "")
    device_info = json.dumps(data.get("deviceInfo", {}))

    user = RustdeskUser.query.filter_by(username=username).first()
    if not user or not check_password(password, user.password_hash):
        return jsonify({"error": "Invalid credentials"}), 401
    if user.status != 1:
        return jsonify({"error": "Account disabled"}), 403

    token_str = create_client_jwt(user.id, user.username)

    tok = UserToken(
        user_id=user.id,
        token=token_str,
        device_id=device_id,
        device_info=device_info,
    )
    db.session.add(tok)
    db.session.commit()

    return jsonify({
        "type": "access_token",
        "access_token": token_str,
        "user": {
            "name": user.username,
            "email": user.email or "",
            "status": user.status,
        },
    })


@bp.route("/logout", methods=["POST"])
def logout():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        UserToken.query.filter_by(token=auth[7:]).delete()
        db.session.commit()
    return jsonify({})


# ── Heartbeat ───────────────────────────────────────────────────────

@bp.route("/heartbeat", methods=["POST"])
def heartbeat():
    data = request.get_json(silent=True) or {}
    peer_id = data.get("id", "")
    peer_uuid = data.get("uuid", "")
    uid = peer_id or peer_uuid
    if uid:
        now = datetime.now(timezone.utc)
        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip()
        hb = db.session.get(Heartbeat, uid)
        is_new = hb is None
        if hb:
            hb.ip = client_ip
            if (now - hb.last_seen).total_seconds() > 30:
                hb.last_seen = now
            if data.get("local_addr"):
                hb.local_ip = _extract_ip(data["local_addr"])
            if data.get("hostname"):
                hb.hostname = data["hostname"]
            if data.get("version"):
                hb.version = data["version"]
        else:
            hb = Heartbeat(
                id=uid, uuid=peer_uuid or uid,
                ip=client_ip, last_seen=now,
                local_ip=_extract_ip(data.get("local_addr", "")),
                hostname=data.get("hostname", ""),
                version=data.get("version", ""),
            )
            db.session.add(hb)
        db.session.commit()

        if is_new:
            try:
                from routes.users import sync_admin_address_books
                sync_admin_address_books()
            except Exception:
                pass
    return jsonify({})


def _extract_ip(addr_str):
    """Extract IP from socket address like '192.168.1.10:12345' or plain IP."""
    if not addr_str:
        return ""
    s = str(addr_str)
    if "]:" in s:
        return s.split("]:")[0].lstrip("[")
    if s.count(":") == 1:
        return s.rsplit(":", 1)[0]
    return s


# ── Sysinfo ─────────────────────────────────────────────────────────

@bp.route("/sysinfo", methods=["POST"])
def sysinfo():
    data = request.get_json(silent=True) or {}
    uid = data.get("id", "")
    if uid:
        hb = db.session.get(Heartbeat, uid)
        if hb:
            if data.get("hostname"):
                hb.hostname = data["hostname"]
            if data.get("os"):
                hb.os_info = data["os"]
            if data.get("version"):
                hb.version = data["version"]
            if data.get("local_ip"):
                hb.local_ip = data["local_ip"]
            if data.get("local_addr"):
                hb.local_ip = _extract_ip(data["local_addr"])
            if data.get("ip"):
                lip = _extract_ip(data["ip"])
                if lip and _is_private_ip(lip):
                    hb.local_ip = lip
            db.session.commit()
    return jsonify({"data": "SYSINFO_UPDATED"})


def _is_private_ip(ip_str):
    """Check if an IP is a private/local address."""
    try:
        parts = ip_str.split(".")
        if len(parts) != 4:
            return False
        a, b = int(parts[0]), int(parts[1])
        return (a == 10 or (a == 172 and 16 <= b <= 31) or
                (a == 192 and b == 168) or a == 127)
    except (ValueError, IndexError):
        return False


@bp.route("/sysinfo_ver", methods=["POST"])
def sysinfo_ver():
    return jsonify({"data": "1.0.0"})


# ── Current user ────────────────────────────────────────────────────

@bp.route("/currentUser", methods=["GET"])
@bp.route("/user/info", methods=["GET"])
def current_user():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({
        "name": user.username,
        "email": user.email or "",
        "status": user.status,
    })


# ── Peers ───────────────────────────────────────────────────────────

@bp.route("/peers", methods=["GET"])
def peers():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    import rustdesk_db
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("pageSize", 50, type=int)
    items, total = rustdesk_db.get_all_peers(page=page, per_page=page_size)
    return jsonify({"data": items, "total": total})


# ── Users list (for client) ────────────────────────────────────────

@bp.route("/users", methods=["GET"])
def users_list():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    page = request.args.get("page", 1, type=int)
    page_size = request.args.get("pageSize", 50, type=int)
    q = RustdeskUser.query.filter_by(status=1)
    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return jsonify({
        "data": [{"name": u.username, "email": u.email or ""} for u in items],
        "total": total,
    })


# ── Address Book ────────────────────────────────────────────────────

@bp.route("/ab", methods=["GET"])
def ab_get():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    book = AddressBook.query.filter_by(user_id=user.id, name="default").first()
    if not book:
        return jsonify({"data": json.dumps({"peers": [], "tags": []})})
    peers = json.loads(book.peers_json or "[]")
    _inject_server_aliases(peers)
    ab_obj = {
        "peers": peers,
        "tags": json.loads(book.tags_json or "[]"),
    }
    return jsonify({"data": json.dumps(ab_obj)})


@bp.route("/ab", methods=["POST"])
def ab_update():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    raw = data.get("data", data)
    if isinstance(raw, str):
        try:
            ab_data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            ab_data = {}
    else:
        ab_data = raw

    book = AddressBook.query.filter_by(user_id=user.id, name="default").first()
    if not book:
        book = AddressBook(user_id=user.id, name="default")
        db.session.add(book)

    if "peers" in ab_data:
        incoming_peers = ab_data["peers"]
        _inject_server_aliases(incoming_peers)
        book.peers_json = json.dumps(incoming_peers)
    if "tags" in ab_data:
        book.tags_json = json.dumps(ab_data["tags"])
    db.session.commit()
    return jsonify({})


@bp.route("/ab/personal", methods=["POST"])
def ab_personal():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    book = AddressBook.query.filter_by(user_id=user.id, name="default").first()
    if not book:
        return jsonify({"data": json.dumps({"peers": [], "tags": [], "guid": ""})})
    peers = json.loads(book.peers_json or "[]")
    _inject_server_aliases(peers)
    ab_obj = {
        "guid": book.guid,
        "peers": peers,
        "tags": json.loads(book.tags_json or "[]"),
    }
    return jsonify({"data": json.dumps(ab_obj)})


@bp.route("/ab/settings", methods=["POST"])
def ab_settings():
    return jsonify({"data": {}})


@bp.route("/ab/shared/profiles", methods=["POST"])
def ab_shared_profiles():
    return jsonify({"data": [], "total": 0})


@bp.route("/ab/peers", methods=["POST"])
def ab_peers():
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    ab_guid = data.get("ab", "")
    book = None
    if ab_guid:
        book = AddressBook.query.filter_by(user_id=user.id, guid=ab_guid).first()
    if not book:
        book = AddressBook.query.filter_by(user_id=user.id, name="default").first()
    if not book:
        return jsonify({"data": [], "total": 0})
    peers = json.loads(book.peers_json or "[]")
    _inject_server_aliases(peers)
    return jsonify({"data": peers, "total": len(peers)})


def _get_or_create_book(user, guid=None):
    if guid:
        book = AddressBook.query.filter_by(user_id=user.id, guid=guid).first()
        if book:
            return book
    book = AddressBook.query.filter_by(user_id=user.id, name="default").first()
    if not book:
        book = AddressBook(user_id=user.id, name="default")
        db.session.add(book)
        db.session.commit()
    return book


@bp.route("/ab/peer/add/<guid>", methods=["POST"])
def ab_peer_add(guid):
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    book = _get_or_create_book(user, guid)
    peers = json.loads(book.peers_json or "[]")
    new_peer = data.get("data", data)
    if isinstance(new_peer, dict):
        peer_id = new_peer.get("id", "")
        tag = PeerTag.query.filter_by(peer_id=peer_id).first()
        if tag and tag.alias:
            new_peer["alias"] = tag.alias
        peers = [p for p in peers if (p.get("id") if isinstance(p, dict) else p) != peer_id]
        peers.append(new_peer)
    book.peers_json = json.dumps(peers)
    db.session.commit()
    return jsonify({})


@bp.route("/ab/peer/update/<guid>", methods=["PUT"])
def ab_peer_update(guid):
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    updated = data.get("data", data)
    peer_id = updated.get("id", guid)
    book = AddressBook.query.filter_by(user_id=user.id, name="default").first()
    if not book:
        return jsonify({"error": "Not found"}), 404
    peers = json.loads(book.peers_json or "[]")
    for i, p in enumerate(peers):
        pid = p.get("id") if isinstance(p, dict) else p
        if pid == peer_id:
            if isinstance(updated, dict) and isinstance(p, dict):
                p.update(updated)
            else:
                peers[i] = updated
            break
    _inject_server_aliases(peers)
    book.peers_json = json.dumps(peers)
    db.session.commit()
    return jsonify({})


@bp.route("/ab/peer/<guid>", methods=["DELETE"])
def ab_peer_delete(guid):
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    peer_ids = data.get("id", [guid])
    if isinstance(peer_ids, str):
        peer_ids = [peer_ids]
    book = AddressBook.query.filter_by(user_id=user.id, name="default").first()
    if not book:
        return jsonify({})
    peers = json.loads(book.peers_json or "[]")
    peers = [p for p in peers if (p.get("id") if isinstance(p, dict) else p) not in peer_ids]
    book.peers_json = json.dumps(peers)
    db.session.commit()
    return jsonify({})


@bp.route("/ab/tags/<guid>", methods=["POST"])
def ab_tags_list(guid):
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    book = _get_or_create_book(user, guid)
    tags = json.loads(book.tags_json or "[]")
    return jsonify({"data": tags, "total": len(tags)})


@bp.route("/ab/tag/add/<guid>", methods=["POST"])
def ab_tag_add(guid):
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    book = _get_or_create_book(user, guid)
    tags = json.loads(book.tags_json or "[]")
    new_tag = data.get("name", data.get("data", ""))
    if new_tag and new_tag not in [t.get("name", t) if isinstance(t, dict) else t for t in tags]:
        tag_entry = {"name": new_tag, "color": data.get("color", "")} if data.get("color") else new_tag
        tags.append(tag_entry)
    book.tags_json = json.dumps(tags)
    db.session.commit()
    return jsonify({})


@bp.route("/ab/tag/rename/<guid>", methods=["PUT"])
def ab_tag_rename(guid):
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    old_name = data.get("old", "")
    new_name = data.get("new", "")
    book = AddressBook.query.filter_by(user_id=user.id, name="default").first()
    if book and old_name and new_name:
        tags = json.loads(book.tags_json or "[]")
        for i, t in enumerate(tags):
            name = t.get("name") if isinstance(t, dict) else t
            if name == old_name:
                tags[i] = {"name": new_name, "color": t.get("color", "")} if isinstance(t, dict) else new_name
                break
        book.tags_json = json.dumps(tags)
        db.session.commit()
    return jsonify({})


@bp.route("/ab/tag/update/<guid>", methods=["PUT"])
def ab_tag_update(guid):
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    book = AddressBook.query.filter_by(user_id=user.id, name="default").first()
    if book:
        tags = json.loads(book.tags_json or "[]")
        tag_name = data.get("name", "")
        for i, t in enumerate(tags):
            name = t.get("name") if isinstance(t, dict) else t
            if name == tag_name:
                tags[i] = {"name": tag_name, "color": data.get("color", "")}
                break
        book.tags_json = json.dumps(tags)
        db.session.commit()
    return jsonify({})


@bp.route("/ab/tag/<guid>", methods=["DELETE"])
def ab_tag_delete(guid):
    user = _get_current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    tag_name = data.get("name", guid)
    book = AddressBook.query.filter_by(user_id=user.id, name="default").first()
    if book:
        tags = json.loads(book.tags_json or "[]")
        tags = [t for t in tags if (t.get("name") if isinstance(t, dict) else t) != tag_name]
        book.tags_json = json.dumps(tags)
        db.session.commit()
    return jsonify({})


# ── Audit ───────────────────────────────────────────────────────────

@bp.route("/audit/conn", methods=["POST"])
def audit_conn():
    data = request.get_json(silent=True) or {}

    from_peer = data.get("id", data.get("from", data.get("from_peer", "")))

    peer_field = data.get("peer", data.get("to", data.get("to_peer", "")))
    if isinstance(peer_field, list):
        to_peer = peer_field[0] if peer_field else ""
    else:
        to_peer = str(peer_field) if peer_field else ""

    fp = str(from_peer or "").strip()
    tp = str(to_peer or "").strip()
    cid = str(data.get("conn_id", "") or "").strip()
    sid = str(data.get("session_id", data.get("uuid", "")) or "").strip()
    fp, tp = _backfill_audit_endpoints(fp, tp, cid, sid)
    # RustDesk audit: id / peer sırası paneldeki Kaynak / Hedef ile genelde terstir.
    if Config.CONN_AUDIT_PEER_SWAP:
        fp, tp = tp, fp

    log = ConnectionLog(
        conn_id=str(data.get("conn_id", "")),
        from_peer=fp,
        to_peer=tp,
        action=data.get("action", "connect"),
        ip=data.get("ip", request.remote_addr or ""),
        session_id=str(data.get("session_id", data.get("uuid", ""))),
    )
    db.session.add(log)
    db.session.commit()
    return jsonify({})


@bp.route("/audit/file", methods=["POST"])
def audit_file():
    data = request.get_json(silent=True) or {}
    entry = FileAudit(
        conn_id=str(data.get("conn_id", "")),
        peer_id=data.get("peer_id", ""),
        path=data.get("path", ""),
        action=data.get("action", ""),
        info=json.dumps(data.get("info", {})),
    )
    db.session.add(entry)
    db.session.commit()
    return jsonify({})


# ── Server config (for web client) ─────────────────────────────────

@bp.route("/server-config", methods=["POST"])
def server_config():
    return jsonify({"data": {}})


@bp.route("/server-config-v2", methods=["POST"])
def server_config_v2():
    return jsonify({"data": {}})
