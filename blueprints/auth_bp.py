# blueprints/auth_bp.py
import os
import uuid
import imghdr
import smtplib
import secrets
from datetime import datetime, timedelta
from email.message import EmailMessage
from flask import Blueprint, request, jsonify, current_app, url_for
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity, get_jwt
)
from models import db, User, UserSession, UniversityDomain, AuditLog  # assumes models.py exists
from sqlalchemy.exc import IntegrityError
from PIL import Image

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# Allowed extensions & limits
ALLOWED_EXT = {'png', 'jpg', 'jpeg'}
MAX_PHOTO_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_PHOTO_DIM = (1024, 1024)  # max width, height


def is_allowed_filename(filename):
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in ALLOWED_EXT

def detect_image_type(path):
    # imghdr.what is limited but combined with Pillow check below
    return imghdr.what(path)

def save_profile_photo(file_storage, user_email):
    """
    Validate & save the uploaded image. Returns public accessible relative path.
    Raises ValueError on invalid.
    """
    cfg = current_app.config
    upload_folder = cfg.get('UPLOAD_FOLDER', 'static/uploads/profile_photos')
    os.makedirs(upload_folder, exist_ok=True)

    filename = secure_filename(file_storage.filename)
    if not filename:
        raise ValueError("Invalid filename")
    if not is_allowed_filename(filename):
        raise ValueError("File extension not allowed")

    # read a bit to check size without loading all at once
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > cfg.get('MAX_CONTENT_LENGTH', MAX_PHOTO_BYTES):
        raise ValueError("File too large")

    # Save to a temp path then open with PIL to verify/normalize
    unique = secrets.token_hex(8)
    base, ext = os.path.splitext(filename)
    safe_name = f"{base}_{unique}{ext}"
    tmp_path = os.path.join(upload_folder, f"tmp_{safe_name}")
    final_path = os.path.join(upload_folder, safe_name)

    file_storage.save(tmp_path)

    # verify with imghdr and PIL
    img_type = detect_image_type(tmp_path)
    if img_type not in ('jpeg', 'png'):
        os.remove(tmp_path)
        raise ValueError("Invalid image type")

    try:
        img = Image.open(tmp_path)
        img.verify()  # verify integrity
    except Exception:
        os.remove(tmp_path)
        raise ValueError("Corrupt or unsupported image")

    # reopen for processing
    img = Image.open(tmp_path)
    img = img.convert('RGB')  # normalize
    img.thumbnail(MAX_PHOTO_DIM, Image.ANTIALIAS)
    img.save(final_path, optimize=True, quality=85)
    os.remove(tmp_path)

    # return relative path (to be served by Flask static)
    rel = os.path.relpath(final_path, cfg.get('STATIC_FOLDER', 'static'))
    return f"/static/{rel.replace(os.path.sep, '/')}"

def generate_verification_token():
    # a short random token; could also be a signed JWT with short expiry
    return secrets.token_urlsafe(24)

# ---- Helper: validate UDG email domain ----
def get_domain_from_email(email):
    try:
        return email.split('@', 1)[1].lower()
    except Exception:
        return ''

def is_valid_udg_email(email):
    domain = get_domain_from_email(email)
    return UniversityDomain.query.filter_by(domain=domain).first() is not None

# ---- Endpoint: register-udg ----
@auth_bp.route('/register-udg', methods=['POST'])
def register_udg():
    """
    Expects multipart/form-data:
      - full_name
      - email
      - password
      - optional: photo (file)
    Flow:
      - validate domain @alumnos.udg.mx or @udg.mx
      - create user (is_verified=False)
      - store temp verification token
      - send verification email (via configured SMTP)
    """
    data = request.form
    full_name = data.get('full_name', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    photo = request.files.get('photo')

    if not full_name or not email or not password:
        return jsonify({'msg': 'full_name, email and password are required'}), 400

    if len(password) < current_app.config.get('MIN_PASSWORD_LENGTH', 8):
        return jsonify({'msg': 'password too short'}), 400

    if not is_valid_udg_email(email):
        return jsonify({'msg': 'email must be an institutional UDG email'}), 400

    # optional photo handling
    profile_photo_url = current_app.config.get('DEFAULT_PROFILE_PHOTO', '/static/images/default_profile.png')
    if photo:
        try:
            profile_photo_url = save_profile_photo(photo, email)
        except ValueError as e:
            return jsonify({'msg': 'photo error', 'detail': str(e)}), 400

    # create user
    hashed = generate_password_hash(password)
    user = User(full_name=full_name, email=email, hashed_password=hashed,
                profile_photo=profile_photo_url, is_verified=False)
    # assign faculty if mapping exists
    domain = get_domain_from_email(email)
    dom = UniversityDomain.query.filter_by(domain=domain).first()
    if dom:
        user.faculty = dom.faculty

    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({'msg': 'email already registered'}), 400

    # generate verification token and save in AuditLog (or separate table)
    token = generate_verification_token()
    # store token in AuditLog for simplicity; in production create explicit VerificationToken model
    db.session.add(AuditLog(user_id=user.id, action='verification_token', data={'token': token}))
    db.session.commit()

    # assemble verification link
    verify_url = url_for('auth.verify_udg_email', _external=True) + f"?token={token}&email={email}"

    # send email (best-effort)
    try:
        send_verification_email(email, full_name, verify_url)
    except Exception as e:
        current_app.logger.exception("Failed to send verification email")
        # still allow registration but warn
        return jsonify({'msg': 'registered_but_email_failed', 'detail': str(e)}), 201

    # audit log
    db.session.add(AuditLog(user_id=user.id, action='register', data={'email': email, 'photo': profile_photo_url}))
    db.session.commit()

    return jsonify({'msg': 'registered', 'detail': 'verification_sent'}), 201

# ---- Email sender (smtplib) ----
def send_verification_email(to_email, full_name, verify_url):
    """
    Uses SMTP settings from app config:
      MAIL_SERVER, MAIL_PORT, MAIL_USERNAME, MAIL_PASSWORD, MAIL_USE_TLS
    """
    cfg = current_app.config
    mail_server = cfg.get('MAIL_SERVER')
    mail_port = cfg.get('MAIL_PORT', 25)
    mail_user = cfg.get('MAIL_USERNAME')
    mail_pass = cfg.get('MAIL_PASSWORD')
    mail_from = cfg.get('MAIL_DEFAULT_SENDER', f"no-reply@{cfg.get('MAIL_DOMAIN','udg.mx')}")

    if not mail_server:
        raise RuntimeError("MAIL_SERVER not configured")

    msg = EmailMessage()
    msg['Subject'] = 'Verificación de cuenta — Chat UDG'
    msg['From'] = mail_from
    msg['To'] = to_email
    body = f"""Hola {full_name},

Para activar tu cuenta en el Chat UDG, haz clic en el siguiente enlace:

{verify_url}

Si no solicitaste esta acción, ignora este correo.

Atentamente,
Equipo Chat UDG
"""
    msg.set_content(body)

    # connect & send
    if cfg.get('MAIL_USE_TLS', False):
        server = smtplib.SMTP(mail_server, mail_port, timeout=10)
        server.starttls()
    else:
        server = smtplib.SMTP(mail_server, mail_port, timeout=10)

    if mail_user and mail_pass:
        server.login(mail_user, mail_pass)

    server.send_message(msg)
    server.quit()

# ---- Endpoint: verify-udg-email ----
@auth_bp.route('/verify-udg-email', methods=['GET', 'POST'])
def verify_udg_email():
    """
    GET usage: /auth/verify-udg-email?token=...&email=...
    POST usage: JSON {'token': '...', 'email':'...'}
    Validates token by searching AuditLog entry (or VerificationToken table).
    Activates user.is_verified = True
    """
    if request.method == 'GET':
        token = request.args.get('token')
        email = request.args.get('email', '').lower()
    else:
        body = request.json or {}
        token = body.get('token')
        email = (body.get('email') or '').lower()

    if not token or not email:
        return jsonify({'msg': 'token and email required'}), 400

    # find audit log for this token
    log = AuditLog.query.filter(
        AuditLog.action == 'verification_token',
        AuditLog.data['token'].astext == token
    ).order_by(AuditLog.ts.desc()).first()

    if not log:
        return jsonify({'msg': 'invalid token'}), 400

    user = User.query.get(log.user_id)
    if not user or user.email != email:
        return jsonify({'msg': 'invalid token / email mismatch'}), 400

    if user.is_verified:
        return jsonify({'msg': 'already_verified'}), 200

    user.is_verified = True
    db.session.add(AuditLog(user_id=user.id, action='verified', data={}))
    db.session.commit()

    return jsonify({'msg': 'verified'}), 200

# ---- Endpoint: udg-login ----
@auth_bp.route('/udg-login', methods=['POST'])
def udg_login():
    """
    Expects JSON: { "email": "...", "password": "..." }
    Returns access_token & refresh_token
    Stores session with JTI for revocation support.
    """
    data = request.json or {}
    email = (data.get('email') or '').lower()
    password = data.get('password', '')

    if not email or not password:
        return jsonify({'msg': 'email and password required'}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.hashed_password, password):
        return jsonify({'msg': 'invalid credentials'}), 401

    if not user.is_verified:
        return jsonify({'msg': 'email_not_verified'}), 403

    additional_claims = {
        'email': user.email,
        'role': user.role,
        'faculty': user.faculty,
        'profile_photo': user.profile_photo
    }
    access_expires = current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', timedelta(hours=1))
    refresh_expires = current_app.config.get('JWT_REFRESH_TOKEN_EXPIRES', timedelta(days=1))

    access_token = create_access_token(identity=user.id, additional_claims=additional_claims, expires_delta=access_expires)
    refresh_token = create_refresh_token(identity=user.id, expires_delta=refresh_expires)

    # save session with token JTI (we need to extract JTI from token)
    # Flask-JWT-Extended exposes callback to get jti on create; lacking that, decode token
    from flask_jwt_extended import decode_token
    access_jti = decode_token(access_token)['jti']
    refresh_jti = decode_token(refresh_token)['jti']

    now = datetime.utcnow()
    sess = UserSession(user_id=user.id, token_jti=access_jti,
                       issued_at=now,
                       expires_at=now + access_expires,
                       active=True)
    db.session.add(sess)
    db.session.add(AuditLog(user_id=user.id, action='login', data={'ip': request.remote_addr}))
    db.session.commit()

    return jsonify({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'expires_in': int(access_expires.total_seconds())
    }), 200

# ---- Endpoint: refresh ----
@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    user = User.query.get(identity)
    if not user:
        return jsonify({'msg': 'invalid user'}), 401
    additional_claims = {
        'email': user.email,
        'role': user.role,
        'faculty': user.faculty,
        'profile_photo': user.profile_photo
    }
    access_expires = current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', timedelta(hours=1))
    new_access = create_access_token(identity=identity, additional_claims=additional_claims, expires_delta=access_expires)
    # store new session JTI
    from flask_jwt_extended import decode_token
    new_jti = decode_token(new_access)['jti']
    now = datetime.utcnow()
    sess = UserSession(user_id=user.id, token_jti=new_jti, issued_at=now,
                       expires_at=now + access_expires, active=True)
    db.session.add(sess)
    db.session.commit()
    return jsonify({'access_token': new_access, 'expires_in': int(access_expires.total_seconds())}), 200
