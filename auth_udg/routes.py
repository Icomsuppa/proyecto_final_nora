import os
import uuid
import jwt
from datetime import datetime, timedelta
from flask import (
    Blueprint, request, jsonify, current_app,
    render_template, redirect, url_for, session as flask_session
)
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
from flask_cors import cross_origin
from models import db, User, Faculty, UserSession

# ============================================================
# 🔹 BLUEPRINT
# ============================================================
auth_udg_bp = Blueprint('auth_udg_bp', __name__, url_prefix='/auth_udg')

# ============================================================
# 🔧 CONFIGURACIONES BASE
# ============================================================
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
UPLOAD_FOLDER = 'static/uploads/profile_images'


# ============================================================
# 🔹 FUNCIONES AUXILIARES
# ============================================================
def allowed_file(filename):
    """Verifica si el archivo tiene una extensión válida."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_jwt(user_id):
    """Genera un token JWT con expiración de 6 horas."""
    expiration = datetime.utcnow() + timedelta(hours=6)
    token = jwt.encode({'user_id': user_id, 'exp': expiration}, 'super-secret-key', algorithm='HS256')
    return token, expiration


# ============================================================
# 🔹 VISTAS HTML (formularios)
# ============================================================
@auth_udg_bp.route('/login', methods=['GET'])
def login_view():
    """Muestra el formulario de inicio de sesión."""
    return render_template('login.html')


@auth_udg_bp.route('/register', methods=['GET'])
def register_view():
    """Muestra el formulario de registro."""
    return render_template('register.html')


# ============================================================
# 🔹 REGISTRO (POST)
# ============================================================
@auth_udg_bp.route('/register', methods=['POST'])
@cross_origin()
def register():
    """Registra un usuario UDG."""
    data = request.form if request.form else request.json
    full_name = data.get('full_name')
    email = data.get('email')
    password = data.get('password')
    faculty_id = data.get('faculty_id')

    if not all([full_name, email, password]):
        return jsonify({'error': 'Faltan campos obligatorios.'}), 400

    if not email.endswith('.udg.mx'):
        return jsonify({'error': 'Solo se permiten correos institucionales de la UDG.'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'error': 'Este correo ya está registrado.'}), 400

    user = User(full_name=full_name, email=email, faculty_id=faculty_id)
    user.set_password(password)
    user.verification_token = str(uuid.uuid4())

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
    """Verifica la cuenta del usuario usando su token único."""
    user = User.query.filter_by(verification_token=token).first()

    if not user:
        return jsonify({'error': 'Token de verificación inválido.'}), 404

    user.is_verified = True
    user.verification_token = None
    db.session.commit()

    return jsonify({'message': 'Cuenta verificada correctamente. Ya puedes iniciar sesión.'}), 200


# ============================================================
# 🔹 LOGIN (POST)
# ============================================================
from flask import render_template, request, redirect, url_for, session as flask_session

@auth_udg_bp.route('/login', methods=['GET', 'POST'])
@cross_origin()
def login():
    if request.method == 'GET':
        return render_template('login.html')

    email = request.form.get('email')
    password = request.form.get('password')
    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return render_template('login.html', error="Credenciales inválidas.")

    if not user.is_verified:
        return render_template('login.html', error="Cuenta no verificada.")

    token, expiration = generate_jwt(user.id)

    # Guardar sesión
    flask_session['user_id'] = user.id
    flask_session['jwt_token'] = token

    # Registrar sesión en BD
    db.session.add(UserSession(
        user_id=user.id,
        jwt_token=token,
        ip_address=request.remote_addr,
        created_at=datetime.utcnow(),
        expires_at=expiration
    ))
    db.session.commit()

    # 🔁 Redirige a la interfaz visual del chat
    return redirect(url_for('chat_bp.chat_view'))

# ============================================================
# 🔹 SUBIR FOTO DE PERFIL
# ============================================================
@auth_udg_bp.route('/profile/upload', methods=['POST'])
def upload_profile_image():
    """Sube o actualiza la foto de perfil del usuario."""
    user_id = request.form.get('user_id')
    file = request.files.get('image')

    if not file or not allowed_file(file.filename):
        return jsonify({'error': 'Archivo inválido. Solo PNG, JPG o JPEG.'}), 400

    filename = secure_filename(f"user_{user_id}_{file.filename}")
    save_path = os.path.join(UPLOAD_FOLDER, filename)

    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    file.save(save_path)

    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuario no encontrado.'}), 404

    user.profile_image = save_path
    db.session.commit()

    return jsonify({'message': 'Imagen actualizada correctamente.', 'path': save_path}), 200


# ============================================================
# 🔹 CIERRE DE SESIÓN
# ============================================================
@auth_udg_bp.route('/logout', methods=['POST'])
def logout():
    """Cierra la sesión del usuario y elimina el token JWT."""
    data = request.json
    token = data.get('token')

    session = UserSession.query.filter_by(jwt_token=token).first()
    if session:
        db.session.delete(session)
        db.session.commit()
        return jsonify({'message': 'Sesión cerrada correctamente.'}), 200

    return jsonify({'error': 'Token inválido o sesión no encontrada.'}), 404
