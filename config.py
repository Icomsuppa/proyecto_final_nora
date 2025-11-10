# config.py
import os

# --- Variables globales (compatibilidad con importaciones antiguas) ---
MULTICAST_GROUP = "224.0.0.1"
MULTICAST_PORT = 5007
TOKEN_EXPIRATION_MINUTES = 60
JWT_HEADER_TYPE = "Bearer"

# --- Clase Config (para app.config.from_object(Config)) ---
class Config:
    # Seguridad
    SECRET_KEY = os.environ.get("SECRET_KEY", "clave_super_segura_de_desarrollo")
    JWT_SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "jwt_clave_super_segura_dev")

    # Debug
    DEBUG = os.environ.get("FLASK_DEBUG", "1") == "1"

    # Rutas / directorios
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "temp_uploads")
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    # Base de datos (SQLite por defecto)
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(BASE_DIR, 'database.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Multicast (mantener aquí también para acceso vía current_app.config)
    MULTICAST_GROUP = MULTICAST_GROUP
    MULTICAST_PORT = MULTICAST_PORT

    # Otros
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # 2 MB por archivo (ej.)
    TOKEN_EXPIRATION_MINUTES = TOKEN_EXPIRATION_MINUTES
    JWT_HEADER_TYPE = JWT_HEADER_TYPE
