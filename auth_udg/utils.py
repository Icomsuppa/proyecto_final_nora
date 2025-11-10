import re, jwt, os
from datetime import datetime, timedelta
from flask import current_app
from itsdangerous import URLSafeTimedSerializer

# Verificar dominio válido UDG
def is_valid_udg_email(email: str) -> bool:
    pattern = r'^[\w\.-]+@(alumnos\.udg\.mx|udg\.mx)$'
    return re.match(pattern, email) is not None


# Extraer facultad por dominio o subdominio (simplificado)
def extract_faculty_from_email(email: str) -> str:
    # Ejemplo: alumno@cucea.udg.mx → Facultad CUCEA
    match = re.search(r'@([\w\-]+)\.udg\.mx', email)
    if match:
        return match.group(1).upper()
    return "GENERAL"


# Generar token de verificación temporal (24h)
def generate_verification_token(email: str) -> str:
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt='udg-verification')


def verify_token(token: str, max_age=86400):  # 24h
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt='udg-verification', max_age=max_age)
        return email
    except Exception:
        return None


# Generar JWT para sesiones
def generate_jwt(user_id, role, faculty):
    payload = {
        "user_id": user_id,
        "role": role,
        "faculty": faculty,
        "exp": datetime.utcnow() + timedelta(hours=6)
    }
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm="HS256")
