import os

from flask import Flask, send_from_directory
from flask_cors import CORS

from config import Config
from models import AdminUser, db


def create_app():
    app = Flask(__name__, static_folder="static", static_url_path="/static")
    app.config.from_object(Config)

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
        _ensure_admin(app)

    @app.route("/")
    @app.route("/admin")
    @app.route("/admin/<path:path>")
    def serve_spa(**kwargs):
        return send_from_directory("templates", "index.html")

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
