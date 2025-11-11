# app/auth/routes.py
from flask import (
    Blueprint, request, jsonify, render_template, redirect, url_for, session as flask_session
)
from flask_cors import cross_origin
from datetime import datetime
from models import db, User, UserSession

from auth_udg.utils import (
    is_valid_udg_email, extract_faculty_from_email,
    generate_verification_token, verify_token,
    generate_jwt
)

auth_udg_bp = Blueprint('auth_udg_bp', __name__, url_prefix='/auth')



# ============================================================
# 🔹 VISTAS HTML
# ============================================================
@auth_udg_bp.route('/login', methods=['GET'])
def login_view():
    return render_template('login.html')


@auth_udg_bp.route('/register', methods=['GET'])
def register_view():
    return render_template('register.html')


# ============================================================
# 🔹 REGISTRO DE USUARIO
# ============================================================
@auth_udg_bp.route('/register', methods=['POST'])
@cross_origin()
def register():
    data = request.form if request.form else request.json
    full_name = data.get('full_name')
    email = data.get('email')
    password = data.get('password')

    if not all([full_name, email, password]):
        return jsonify({'error': 'Faltan campos obligatorios.'}), 400

    if not is_valid_udg_email(email):
        return jsonify({'error': 'Solo se permiten correos institucionales de la UDG.'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Este correo ya está registrado.'}), 400

    faculty = extract_faculty_from_email(email)
    user = User(full_name=full_name, email=email, faculty_id=faculty)
    user.set_password(password)
    user.verification_token = generate_verification_token(email)

    db.session.add(user)
    db.session.commit()

    verification_link = url_for('auth_udg_bp.verify', token=user.verification_token, _external=True)
    print(f"🔗 Enlace de verificación: {verification_link}")

    return jsonify({
        'message': 'Usuario registrado correctamente. Verifica tu correo institucional.',
        'verification_link': verification_link
    }), 201


# ============================================================
# 🔹 VERIFICACIÓN DE CUENTA
# ============================================================
@auth_udg_bp.route('/verify/<token>', methods=['GET'])
def verify(token):
    email = verify_token(token)
    if not email:
        return jsonify({'error': 'Token inválido o expirado.'}), 400

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'error': 'Usuario no encontrado.'}), 404

    user.is_verified = True
    user.verification_token = None
    db.session.commit()

    return jsonify({'message': 'Cuenta verificada correctamente. Ya puedes iniciar sesión.'}), 200


# ============================================================
# 🔹 LOGIN
# ============================================================
@auth_udg_bp.route('/login', methods=['POST'])
@cross_origin()
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return render_template('login.html', error="Credenciales inválidas.")

    if not user.is_verified:
        return render_template('login.html', error="Cuenta no verificada.")

    token = generate_jwt(user.id, role='user', faculty=user.faculty_id)
    flask_session['user_id'] = user.id
    flask_session['jwt_token'] = token

    # Registrar sesión en la BD
    db.session.add(UserSession(
        user_id=user.id,
        jwt_token=token,
        ip_address=request.remote_addr,
        created_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=6)
    ))
    db.session.commit()

    return redirect(url_for('chat_bp.chat_view'))


# ============================================================
# 🔹 LOGOUT
# ============================================================
@auth_udg_bp.route('/logout', methods=['POST'])
def logout():
    data = request.json
    token = data.get('token')

    session = UserSession.query.filter_by(jwt_token=token).first()
    if session:
        db.session.delete(session)
        db.session.commit()
        return jsonify({'message': 'Sesión cerrada correctamente.'}), 200

    return jsonify({'error': 'Token inválido o sesión no encontrada.'}), 404
