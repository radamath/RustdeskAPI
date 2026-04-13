import uuid
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def _utcnow():
    return datetime.now(timezone.utc)


def _uuid():
    return uuid.uuid4().hex


class AdminUser(db.Model):
    __tablename__ = "admin_user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(120))
    role = db.Column(db.String(20), default="admin")
    is_active = db.Column(db.Boolean, default=True)
    totp_secret = db.Column(db.String(32), nullable=True)
    totp_enabled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=_utcnow)


class RustdeskUser(db.Model):
    __tablename__ = "rustdesk_user"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(120))
    group_id = db.Column(db.Integer, db.ForeignKey("device_group.id"), nullable=True)
    role = db.Column(db.String(20), default="user")  # "admin" or "user"
    status = db.Column(db.Integer, default=1)  # 1=active, 0=disabled
    created_at = db.Column(db.DateTime, default=_utcnow)

    tokens = db.relationship("UserToken", backref="user", lazy=True)
    address_books = db.relationship("AddressBook", backref="user", lazy=True)


class DeviceGroup(db.Model):
    __tablename__ = "device_group"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=_utcnow)

    users = db.relationship("RustdeskUser", backref="group", lazy=True)
    peers = db.relationship("PeerTag", backref="group", lazy=True)


class PeerTag(db.Model):
    """Extra metadata we store for peers that live in RustDesk's own DB."""
    __tablename__ = "peer_tag"
    id = db.Column(db.Integer, primary_key=True)
    peer_id = db.Column(db.String(100), unique=True, nullable=False)
    alias = db.Column(db.String(200), default="")
    tags = db.Column(db.Text, default="[]")  # JSON array
    notes = db.Column(db.Text, default="")
    group_id = db.Column(db.Integer, db.ForeignKey("device_group.id"), nullable=True)


class AddressBook(db.Model):
    __tablename__ = "address_book"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("rustdesk_user.id"), nullable=False)
    guid = db.Column(db.String(32), default=_uuid, unique=True)
    name = db.Column(db.String(100), default="default")
    peers_json = db.Column(db.Text, default="[]")
    tags_json = db.Column(db.Text, default="[]")
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)


class ConnectionLog(db.Model):
    __tablename__ = "connection_log"
    id = db.Column(db.Integer, primary_key=True)
    conn_id = db.Column(db.String(64), default="")
    from_peer = db.Column(db.String(100), nullable=False)
    to_peer = db.Column(db.String(100), nullable=False)
    action = db.Column(db.String(50), default="connect")
    timestamp = db.Column(db.DateTime, default=_utcnow)
    ip = db.Column(db.String(45), default="")
    session_id = db.Column(db.String(64), default="")


class FileAudit(db.Model):
    __tablename__ = "file_audit"
    id = db.Column(db.Integer, primary_key=True)
    conn_id = db.Column(db.String(64), default="")
    peer_id = db.Column(db.String(100), default="")
    path = db.Column(db.Text, default="")
    action = db.Column(db.String(50), default="")
    info = db.Column(db.Text, default="")
    timestamp = db.Column(db.DateTime, default=_utcnow)


class UserToken(db.Model):
    __tablename__ = "user_token"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("rustdesk_user.id"), nullable=False)
    token = db.Column(db.String(512), unique=True, nullable=False)
    device_id = db.Column(db.String(100), default="")
    device_info = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=_utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)


class ApiKey(db.Model):
    __tablename__ = "api_key"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    key_hash = db.Column(db.String(128), nullable=False)
    key_prefix = db.Column(db.String(8), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("admin_user.id"))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=_utcnow)
    last_used = db.Column(db.DateTime, nullable=True)


class Setting(db.Model):
    __tablename__ = "setting"
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, default="")
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)


class AuditLog(db.Model):
    __tablename__ = "audit_log"
    id = db.Column(db.Integer, primary_key=True)
    admin_user_id = db.Column(db.Integer, nullable=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, default="")
    ip_address = db.Column(db.String(45), default="")
    timestamp = db.Column(db.DateTime, default=_utcnow)


class Heartbeat(db.Model):
    __tablename__ = "heartbeat"
    id = db.Column(db.String(100), primary_key=True)  # peer id
    uuid = db.Column(db.String(100), default="")
    ip = db.Column(db.String(45), default="")
    local_ip = db.Column(db.String(45), default="")
    hostname = db.Column(db.String(200), default="")
    os_info = db.Column(db.String(200), default="")
    version = db.Column(db.String(50), default="")
    last_seen = db.Column(db.DateTime, default=_utcnow)
