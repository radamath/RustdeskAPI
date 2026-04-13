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


def get_all_peers(search: str = "", page: int = 1, per_page: int = 50):
    with _conn() as c:
        cur = c.cursor()
        if not _table_exists(cur):
            return [], 0

        count_sql = "SELECT COUNT(*) FROM peer"
        data_sql = "SELECT id, uuid, pk, created_at, \"user\", status, note, info FROM peer"

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

        peers = []
        for row in cur.fetchall():
            info = {}
            try:
                info = json.loads(row["info"]) if row["info"] else {}
            except (json.JSONDecodeError, TypeError):
                pass
            peers.append({
                "id": row["id"],
                "uuid": row["uuid"].hex() if isinstance(row["uuid"], bytes) else str(row["uuid"] or ""),
                "created_at": row["created_at"],
                "user": row["user"].decode("utf-8", errors="replace") if isinstance(row["user"], bytes) else str(row["user"] or ""),
                "status": row["status"],
                "note": row["note"] or "",
                "info": info,
            })
        return peers, total


def get_peer(peer_id: str):
    with _conn() as c:
        cur = c.cursor()
        if not _table_exists(cur):
            return None
        cur.execute(
            'SELECT id, uuid, pk, created_at, "user", status, note, info FROM peer WHERE id = ?',
            (peer_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        info = {}
        try:
            info = json.loads(row["info"]) if row["info"] else {}
        except (json.JSONDecodeError, TypeError):
            pass
        return {
            "id": row["id"],
            "uuid": row["uuid"].hex() if isinstance(row["uuid"], bytes) else str(row["uuid"] or ""),
            "created_at": row["created_at"],
            "user": row["user"].decode("utf-8", errors="replace") if isinstance(row["user"], bytes) else str(row["user"] or ""),
            "status": row["status"],
            "note": row["note"] or "",
            "info": info,
        }


def get_peer_count():
    with _conn() as c:
        cur = c.cursor()
        if not _table_exists(cur):
            return 0
        cur.execute("SELECT COUNT(*) FROM peer")
        return cur.fetchone()[0]
