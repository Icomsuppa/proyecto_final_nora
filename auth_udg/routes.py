# app/auth/routes.py
from flask import (
    Blueprint, request, jsonify, render_template, redirect, url_for, session as flask_session
)
from flask_cors import cross_origin
from datetime import datetime, timedelta
from models import db, User, UserSession
import os
import uuid
from werkzeug.utils import secure_filename

from auth_udg.utils import (
    is_valid_udg_email, extract_faculty_from_email,
    generate_verification_token, verify_token,
    generate_jwt
)

chat_bp = Blueprint('chat_bp', __name__, url_prefix='/chat')
auth_udg_bp = Blueprint('auth_udg_bp', __name__, url_prefix='/auth')

# Configuración de uploads
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, '..', 'static', 'uploads', 'profile_images')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

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
# 🔹 REGISTRO DE USUARIO - VERSIÓN MEJORADA
# ============================================================
@auth_udg_bp.route('/register', methods=['POST'])
@cross_origin()
def register():
    print("🔴🔴🔴 === NUEVO REGISTRO INICIADO ===")
    
    try:
        data = request.form
        full_name = data.get('full_name')
        email = data.get('email')
        password = data.get('password')
        faculty_id = data.get('faculty_id')

        file = request.files.get('profile_image')
        
        # DEBUG MEJORADO
        if file:
            print(f"🟢 ARCHIVO RECIBIDO: {file.filename}")
            print(f"   - content_type: {file.content_type}")
            print(f"   - content_length header: {file.content_length}")
            
            # Verificar tamaño real
            file.seek(0, 2)  # Ir al final
            actual_size = file.tell()
            file.seek(0)  # Volver al inicio
            print(f"   - tamaño real: {actual_size} bytes")
            
            if actual_size > 0:
                print("   - ✅ ARCHIVO TIENE CONTENIDO")
            else:
                print("   - ❌ ARCHIVO VACÍO - posible problema en el formulario")
        else:
            print("🔴 NO SE RECIBIÓ NINGÚN ARCHIVO")

        # Validaciones básicas
        if not all([full_name, email, password, faculty_id]):
            return jsonify({'error': 'Faltan campos obligatorios.'}), 400

        if not is_valid_udg_email(email):
            return jsonify({'error': 'Solo se permiten correos institucionales de la UDG.'}), 400

        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Este correo ya está registrado.'}), 400

        # Crear usuario
        user = User(full_name=full_name, email=email, faculty_id=faculty_id)
        user.set_password(password)
        user.verification_token = str(uuid.uuid4())  # Usamos UUID simple
        
        # Manejo de imagen - VERSIÓN SIMPLIFICADA
        profile_image_path = "uploads/profile_images/default.png"
        if file and file.filename:
            file.seek(0, 2)  # Ir al final para ver tamaño
            file_size = file.tell()
            file.seek(0)  # Volver al inicio
            
            if file_size > 0 and allowed_file(file.filename):
                try:
                    filename = secure_filename(f"user_{uuid.uuid4()}_{file.filename}")
                    save_path = os.path.join(UPLOAD_FOLDER, filename)
                    file.save(save_path)
                    profile_image_path = f"uploads/profile_images/{filename}"
                    print(f"✅ Imagen guardada: {profile_image_path}")
                except Exception as e:
                    print(f"⚠️ Error guardando imagen: {e}")
                    # Continuamos con imagen default si hay error
        
        user.profile_image = profile_image_path

        # Guardar usuario
        db.session.add(user)
        db.session.commit()
        print(f"✅ Usuario guardado: {email}")

        # Enlace de verificación
        verification_link = url_for('auth_udg_bp.verify', token=user.verification_token, _external=True)
        print(f"🔗 Enlace: {verification_link}")

        # ✅ RESPuesta de éxito con redirección
        return jsonify({
            'success': True,
            'message': '✅ Registro exitoso. Revisa tu correo para verificar tu cuenta.',
            'redirect_url': url_for('auth_udg_bp.login_view')
        }), 201

    except Exception as e:
        print(f"❌ ERROR GENERAL: {e}")
        return jsonify({'error': 'Error interno del servidor.'}), 500

# ============================================================
# 🔹 VERIFICACIÓN DE CUENTA 
# ============================================================
@auth_udg_bp.route('/verify/<token>', methods=['GET'])
def verify(token):
    try:
        user = User.query.filter_by(verification_token=token).first()
        
        if not user:
            print(f"❌ Token inválido: {token}")
            return render_template('verification_result.html', 
                                success=False, 
                                message="Token de verificación inválido o expirado.")
        
        user.is_verified = True
        user.verification_token = None
        db.session.commit()
        
        print(f"✅ Usuario verificado: {user.email}")
        return render_template('verification_result.html', 
                              success=True, 
                              message="✅ Cuenta verificada exitosamente. Ya puedes iniciar sesión.")
                              
    except Exception as e:
        print(f"❌ Error en verificación: {e}")
        return render_template('verification_result.html', 
                              success=False, 
                              message="Error interno durante la verificación.")

# ============================================================
# 🔹 LOGIN
# ============================================================
@auth_udg_bp.route('/login', methods=['POST'])
@cross_origin()
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    
    if not email or not password:
        return render_template('login.html', error="Por favor completa todos los campos.")
    
    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return render_template('login.html', error="Credenciales inválidas.")

    # Verificación temporalmente desactivada
    # if not user.is_verified:
    #     return render_template('login.html', error="Cuenta no verificada. Revisa tu correo.")

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

@chat_bp.route('/chat')
def chat_view():
    # aquí puedes validar sesión si quieres
    return render_template('index.html')

# ============================================================
# 🔹 LOGOUT
# ============================================================
@auth_udg_bp.route('/logout', methods=['GET'])
def logout():
    user_id = flask_session.get('user_id')
    token = flask_session.get('jwt_token')
    
    flask_session.clear()
    
    if token:
        session = UserSession.query.filter_by(jwt_token=token).first()
        if session:
            db.session.delete(session)
            db.session.commit()
    
    return redirect(url_for('auth_udg_bp.login_view'))