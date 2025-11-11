# app/auth/utils.py
import re
import jwt
from datetime import datetime, timedelta
from typing import Optional
from flask import current_app
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

# ============================================================
# 🔹 CONSTANTES
# ============================================================
VERIFICATION_SALT = 'udg-verification'
VERIFICATION_TOKEN_EXP = 24 * 3600  # 24 horas
JWT_EXP_HOURS = 6
UDG_DOMAINS = ('udg.mx', 'alumnos.udg.mx')


# ============================================================
# 🔹 EMAIL
# ============================================================
def is_valid_udg_email(email: str) -> bool:
    """Verifica si el correo pertenece al dominio UDG permitido."""
    pattern = r'^[\w\.-]+@(' + '|'.join(re.escape(d) for d in UDG_DOMAINS) + r')$'
    return re.fullmatch(pattern, email.lower()) is not None


def extract_faculty_from_email(email: str) -> str:
    """
    Extrae la facultad a partir del subdominio del correo.
    Ejemplo: alumno@cucea.udg.mx -> 'CUCEA'
    """
    match = re.search(r'@([\w\-]+)\.udg\.mx', email.lower())
    if match:
        return match.group(1).upper()
    return "GENERAL"


# ============================================================
# 🔹 VERIFICACIÓN DE CUENTA
# ============================================================
def generate_verification_token(email: str) -> str:
    """Genera un token temporal de verificación de cuenta (24h)."""
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return serializer.dumps(email, salt=VERIFICATION_SALT)


def verify_token(token: str, max_age: int = VERIFICATION_TOKEN_EXP) -> Optional[str]:
    """
    Verifica un token de verificación.
    Devuelve el email si es válido, None si es inválido o expirado.
    """
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt=VERIFICATION_SALT, max_age=max_age)
        return email
    except SignatureExpired:
        # Token válido pero expirado
        return None
    except BadSignature:
        # Token inválido
        return None


# ============================================================
# 🔹 JWT
# ============================================================
def generate_jwt(user_id: int, role: str, faculty: str) -> str:
    """Genera un token JWT para sesión de usuario (6h)."""
    payload = {
        "user_id": user_id,
        "role": role,
        "faculty": faculty,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXP_HOURS)
    }
    token = jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm="HS256")
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    return token
