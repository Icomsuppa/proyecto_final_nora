import os
import uuid
from flask import Blueprint, request, jsonify, render_template, url_for
from werkzeug.utils import secure_filename
from models import db, User
from auth.utils import allowed_file  # Debe contener {'png','jpg','jpeg'}

# Configuración de uploads
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, '..', 'static', 'uploads', 'profile_images')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif'}

# ============================================================
# 🔹 REGISTRO DE USUARIO 
# ============================================================
@auth_udg_bp.route('/register', methods=['POST'])
@cross_origin()
def register():
    print("🔴🔴🔴 === NUEVO REGISTRO INICIADO ===")
    print(f"🔴 DEBUG: request.method = {request.method}")
    print(f"🔴 DEBUG: request.content_type = {request.content_type}")
    print(f"🔴 DEBUG: request.form keys = {list(request.form.keys())}")
    print(f"🔴 DEBUG: request.files keys = {list(request.files.keys())}")
    
    data = request.form
    full_name = data.get('full_name')
    email = data.get('email')
    password = data.get('password')
    faculty_id = data.get('faculty_id')  # ✅ Ahora viene del formulario

    file = request.files.get('profile_image')
    
    # DEBUG EXTREMADAMENTE DETALLADO
    if file and file.filename:
        print(f"🟢 ARCHIVO ENCONTRADO:")
        print(f"   - filename: {file.filename}")
        print(f"   - content_type: {file.content_type}")
        print(f"   - content_length: {file.content_length}")
        
        # Verificar tamaño real
        file.seek(0, 2)  # Ir al final
        file_size = file.tell()
        file.seek(0)  # Volver al inicio
        print(f"   - tamaño real: {file_size} bytes")
    else:
        print("🔴 NO SE ENCONTRÓ ARCHIVO profile_image")

    # Validaciones básicas
    if not all([full_name, email, password, faculty_id]):
        print("❌ Faltan campos obligatorios.")
        return jsonify({'error': 'Faltan campos obligatorios.'}), 400

    if not is_valid_udg_email(email):
        print("❌ Correo no institucional")
        return jsonify({'error': 'Solo se permiten correos institucionales de la UDG.'}), 400

    if User.query.filter_by(email=email).first():
        print("❌ Correo ya registrado")
        return jsonify({'error': 'Este correo ya está registrado.'}), 400

    # Crear usuario (usa faculty_id del formulario, no extraído del email)
    user = User(full_name=full_name, email=email, faculty_id=faculty_id)
    user.set_password(password)
    user.verification_token = str(uuid.uuid4())
    
    # -------------------------
    # Manejo de imagen de perfil
    # -------------------------
    if file and file.filename and file.content_length > 0:
        print(f"🟢 PROCESANDO IMAGEN: {file.filename}")
        if allowed_file(file.filename):
            filename = secure_filename(f"user_{uuid.uuid4()}_{file.filename}")
            save_path = os.path.join(UPLOAD_FOLDER, filename)
            print(f"🟢 RUTA DE GUARDADO: {save_path}")
            
            try:
                file.save(save_path)
                # Verificar que se guardó
                if os.path.exists(save_path):
                    file_stats = os.stat(save_path)
                    print(f"✅ IMAGEN GUARDADA EXITOSAMENTE: {save_path}")
                    print(f"✅ Tamaño del archivo guardado: {file_stats.st_size} bytes")
                    user.profile_image = f"uploads/profile_images/{filename}"
                else:
                    print("❌ ERROR: Archivo no se creó después de save()")
                    user.profile_image = "uploads/profile_images/default.png"
            except Exception as e:
                print(f"❌ ERROR GUARDANDO IMAGEN: {str(e)}")
                user.profile_image = "uploads/profile_images/default.png"
        else:
            print("❌ Archivo no permitido")
            user.profile_image = "uploads/profile_images/default.png"
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

    verification_link = url_for('auth_udg_bp.verify', token=user.verification_token, _external=True)
    print(f"🔗 Enlace de verificación: {verification_link}")

    return jsonify({
        'message': 'Usuario registrado correctamente. Verifica tu correo institucional.',
        'verification_link': verification_link
    }), 201