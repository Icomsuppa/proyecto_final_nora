import os
import uuid
from flask import Blueprint, request, jsonify, render_template, url_for
from werkzeug.utils import secure_filename
from models import db, User
from auth.utils import allowed_file  # Debe contener {'png','jpg','jpeg'}

register_bp = Blueprint('register_bp', __name__, url_prefix='/auth')

# -------------------------
# Carpeta de uploads absoluta
# -------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, '..', 'static', 'uploads', 'profile_images')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
print(f"DEBUG: Carpeta de uploads configurada en: {UPLOAD_FOLDER}")

# -------------------------
# Vista HTML
# -------------------------
@register_bp.route('/register', methods=['GET'])
def register_view():
    return render_template('register.html')

# -------------------------
# Registro POST
# -------------------------
@register_bp.route('/register', methods=['POST'])
def register():
    print("=== NUEVO REGISTRO ===")
    data = request.form
    full_name = data.get('full_name')
    email = data.get('email')
    password = data.get('password')
    faculty_id = data.get('faculty_id')

    print("DEBUG: request.form:", data)
    print("DEBUG: request.files.keys():", list(request.files.keys()))
    
    file = request.files.get('profile_image')
    
    # Validación de existencia de archivo
    if not file:
        print("⚠️ No se envió ningún archivo de imagen.")
    else:
        print(f"✅ Archivo recibido: {file.filename}")
        print(f"DEBUG: content_type={file.content_type}")
        file_bytes = file.read()
        print(f"DEBUG: tamaño del archivo en bytes={len(file_bytes)}")
        file.seek(0)  # Reset para guardar

    # Validaciones básicas
    if not all([full_name, email, password]):
        print("❌ Faltan campos obligatorios.")
        return jsonify({'error': 'Faltan campos obligatorios.'}), 400

    if not email.endswith('.udg.mx'):
        print("❌ Correo no institucional")
        return jsonify({'error': 'Solo se permiten correos institucionales de la UDG.'}), 400

    if User.query.filter_by(email=email).first():
        print("❌ Correo ya registrado")
        return jsonify({'error': 'Este correo ya está registrado.'}), 400

    # Crear usuario
    user = User(full_name=full_name, email=email, faculty_id=faculty_id)
    user.set_password(password)
    user.verification_token = str(uuid.uuid4())
    
    # -------------------------
    # Manejo de imagen de perfil
    # -------------------------
    if file:
        if allowed_file(file.filename):
            filename = secure_filename(f"user_{uuid.uuid4()}_{file.filename}")
            save_path = os.path.join(UPLOAD_FOLDER, filename)
            print(f"DEBUG: Ruta completa para guardar: {save_path}")
            try:
                file.save(save_path)
                user.profile_image = f"uploads/profile_images/{filename}"
                print(f"✅ Imagen guardada correctamente: {user.profile_image}")
            except Exception as e:
                print("❌ ERROR guardando imagen:", e)
                return jsonify({'error': 'No se pudo guardar la imagen.'}), 500
        else:
            print("❌ Archivo no permitido")
            return jsonify({'error': 'Archivo no permitido. Solo png, jpg, jpeg.'}), 400
    else:
        print("INFO: No se envió ninguna imagen, se asigna default")
        user.profile_image = "uploads/profile_images/default.png"

    # Guardar usuario
    try:
        db.session.add(user)
        db.session.commit()
        print(f"✅ Usuario guardado en DB: {email}")
    except Exception as e:
        print("❌ ERROR guardando usuario en DB:", e)
        return jsonify({'error': 'No se pudo guardar el usuario.'}), 500

    verification_link = url_for('register_bp.verify', token=user.verification_token, _external=True)
    print(f"🔗 Enlace de verificación: {verification_link}")

    return jsonify({
        'message': 'Usuario registrado correctamente. Verifica tu correo institucional.',
        'verification_link': verification_link
    }), 201

# -------------------------
# Verificación
# -------------------------
@register_bp.route('/verify/<token>', methods=['GET'])
def verify(token):
    user = User.query.filter_by(verification_token=token).first()
    if not user:
        print("❌ Token inválido")
        return jsonify({'error': 'Token de verificación inválido.'}), 404

    user.is_verified = True
    user.verification_token = None
    db.session.commit()
    print(f"✅ Usuario verificado: {user.email}")
    return jsonify({'message': 'Cuenta verificada correctamente. Ya puedes iniciar sesión.'}), 200
