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

    from routes import auth, api, devices, users, groups, address_book, audit, settings
    for bp in (auth.bp, api.bp, devices.bp, users.bp, groups.bp,
               address_book.bp, audit.bp, settings.bp):
        app.register_blueprint(bp)

    with app.app_context():
        db.create_all()
        _ensure_admin(app)

    @app.route("/")
    @app.route("/admin")
    @app.route("/admin/<path:path>")
    def serve_spa(**kwargs):
        return send_from_directory("templates", "index.html")

    return app


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
