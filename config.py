import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(BASE_DIR, "data"))
os.makedirs(DATA_DIR, exist_ok=True)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(DATA_DIR, 'rustdesk_api.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    RUSTDESK_DB_PATH = os.environ.get(
        "RUSTDESK_DB", os.path.join(BASE_DIR, "db_v2.sqlite3")
    )

    JWT_EXPIRATION_HOURS = int(os.environ.get("JWT_EXPIRATION_HOURS", "24"))
    ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")

    # RDGen Docker servis adresi (örn. http://rdgen:8000). Ayarlıysa build ve durum
    # bu URL üzerinden gider; indirme linkleri API üzerinden proxy'lenir.
    RDGEN_INTERNAL_URL = os.environ.get("RDGEN_INTERNAL_URL", "").strip()

    # Ters proxy arkasında doğru indirme URL'leri için (örn. https://panel.example.com)
    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").strip().rstrip("/")

    # RustDesk /audit/conn gövdesindeki id ↔ peer alanları Kaynak/Hedef ile ters; True iken kayıtta yer değiştirir.
    CONN_AUDIT_PEER_SWAP = os.environ.get("CONN_AUDIT_PEER_SWAP", "1").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )
