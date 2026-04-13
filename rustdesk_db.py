"""Read-only access to RustDesk server's db_v2.sqlite3."""

import json
import sqlite3
from contextlib import contextmanager

_db_path: str = ""


def init(path: str):
    global _db_path
    _db_path = path


@contextmanager
def _conn():
    c = sqlite3.connect(f"file:{_db_path}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    try:
        yield c
    finally:
        c.close()


def _table_exists(cursor) -> bool:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='peer'"
    )
    return cursor.fetchone() is not None


def _get_columns(cursor):
    cursor.execute("PRAGMA table_info(peer)")
    return {row["name"] for row in cursor.fetchall()}


def _parse_info(raw):
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}


def _safe_str(val, encoding="utf-8"):
    if isinstance(val, bytes):
        return val.decode(encoding, errors="replace")
    return str(val or "")


def _row_to_peer(row, columns):
    info = _parse_info(row["info"])
    peer = {
        "id": row["id"],
        "uuid": row["uuid"].hex() if isinstance(row["uuid"], bytes) else str(row["uuid"] or ""),
        "created_at": row["created_at"],
        "user": _safe_str(row["user"]),
        "status": row["status"],
        "note": row["note"] or "",
        "info": info,
    }
    if "ip" in columns:
        peer["ip"] = _safe_str(row["ip"]) if row["ip"] else ""
    if "last_online" in columns:
        peer["last_online"] = row["last_online"] or ""
    return peer


def get_all_peers(search: str = "", page: int = 1, per_page: int = 50):
    with _conn() as c:
        cur = c.cursor()
        if not _table_exists(cur):
            return [], 0

        columns = _get_columns(cur)

        count_sql = "SELECT COUNT(*) FROM peer"
        data_sql = "SELECT * FROM peer"

        params = []
        if search:
            where = " WHERE id LIKE ? OR note LIKE ?"
            count_sql += where
            data_sql += where
            params = [f"%{search}%", f"%{search}%"]

        cur.execute(count_sql, params)
        total = cur.fetchone()[0]

        data_sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        cur.execute(data_sql, params)

        return [_row_to_peer(row, columns) for row in cur.fetchall()], total


def get_peer(peer_id: str):
    with _conn() as c:
        cur = c.cursor()
        if not _table_exists(cur):
            return None

        columns = _get_columns(cur)
        cur.execute("SELECT * FROM peer WHERE id = ?", (peer_id,))
        row = cur.fetchone()
        if not row:
            return None
        return _row_to_peer(row, columns)


def get_peer_count():
    with _conn() as c:
        cur = c.cursor()
        if not _table_exists(cur):
            return 0
        cur.execute("SELECT COUNT(*) FROM peer")
        return cur.fetchone()[0]
