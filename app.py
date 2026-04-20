import os

from flask import Flask, make_response, render_template, request, send_from_directory
from flask_cors import CORS

from config import Config
from models import AdminUser, ConnectionLog, db


def create_app():
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config.from_object(Config)

    if getattr(Config, "TRUST_PROXY", False):
        from werkzeug.middleware.proxy_fix import ProxyFix

        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

    CORS(app, supports_credentials=True)
    db.init_app(app)

    import rustdesk_db
    rustdesk_db.init(app.config["RUSTDESK_DB_PATH"])

    from routes import auth, api, devices, users, groups, address_book, audit, settings, deploy
    for bp in (auth.bp, api.bp, devices.bp, users.bp, groups.bp,
               address_book.bp, audit.bp, settings.bp, deploy.bp):
        app.register_blueprint(bp)

    with app.app_context():
        db.create_all()
        _migrate_schema()
        _migrate_connection_peer_swap_once()
        _ensure_admin(app)

    @app.after_request
    def _static_no_cache(resp):
        if request.path.startswith("/static/"):
            resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            resp.headers["Pragma"] = "no-cache"
        return resp

    @app.route("/")
    @app.route("/admin")
    @app.route("/admin/<path:path>")
    def serve_spa(**kwargs):
        ver = getattr(Config, "STATIC_ASSET_VERSION", "15")
        resp = make_response(render_template("index.html", asset_version=ver))
        resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        return resp

    return app


def _migrate_schema():
    """Add missing columns to existing tables so upgrades don't crash."""
    import sqlite3
    from config import DATA_DIR
    db_path = os.path.join(DATA_DIR, "rustdesk_api.db")
    if not os.path.isfile(db_path):
        return
    conn = sqlite3.connect(db_path)
    migrations = [
        ("admin_user", "totp_secret", "VARCHAR(32)"),
        ("admin_user", "totp_enabled", "BOOLEAN DEFAULT 0"),
        ("heartbeat", "ip", "VARCHAR(45) DEFAULT ''"),
        ("rustdesk_user", "role", "VARCHAR(20) DEFAULT 'user'"),
        ("heartbeat", "local_ip", "VARCHAR(45) DEFAULT ''"),
        ("heartbeat", "hostname", "VARCHAR(200) DEFAULT ''"),
        ("heartbeat", "os_info", "VARCHAR(200) DEFAULT ''"),
        ("heartbeat", "version", "VARCHAR(50) DEFAULT ''"),
    ]
    for table, column, col_type in migrations:
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
        except sqlite3.OperationalError:
            pass

    try:
        conn.execute(
            "DELETE FROM heartbeat WHERE id GLOB '*[^0-9]*'"
        )
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def _migrate_connection_peer_swap_once():
    """Eski connection_log satırlarında Kaynak/Hedef bir kereliğine yer değiştirir (RustDesk id/peer tersliği)."""
    from config import DATA_DIR, Config

    if not getattr(Config, "CONN_AUDIT_PEER_SWAP", True):
        return
    flag = os.path.join(DATA_DIR, ".conn_audit_peer_swap_migrated_v1")
    if os.path.isfile(flag):
        return
    try:
        for row in ConnectionLog.query.all():
            a, b = row.from_peer or "", row.to_peer or ""
            row.from_peer, row.to_peer = b, a
        db.session.commit()
        with open(flag, "w", encoding="utf-8") as f:
            f.write("1")
    except Exception:
        db.session.rollback()


def _ensure_admin(app):
    from routes.auth import hash_password
    username = app.config["ADMIN_USERNAME"]
    if not AdminUser.query.filter_by(username=username).first():
        admin = AdminUser(
            username=username,
            password_hash=hash_password(app.config["ADMIN_PASSWORD"]),
            role="superadmin",
        )
        db.session.add(admin)
        db.session.commit()


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=21114, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
