# =========================================================
# 🧩 app.py — Punto de entrada principal del microservicio Flask
# =========================================================
import os
from flask import Flask, render_template, redirect, url_for, session as flask_session
from flask_jwt_extended import JWTManager
from blueprints.chat_bp import chat_bp, start_listener_thread
from blueprints.time_bp import time_bp
from auth_udg.routes import auth_udg_bp
from models import db
from config import Config

# =========================================================
# 🚀 Inicialización básica de la app
# =========================================================

root_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(root_dir, 'static')
templates_dir = os.path.join(root_dir, 'templates')

app = Flask(__name__,
             template_folder=templates_dir,
             static_folder=static_dir)

# =========================================================
# ⚙️ Configuración Global
# =========================================================

app.config.from_object(Config)

# Inicializar extensiones
db.init_app(app)
jwt = JWTManager(app)

# =========================================================
# 🔗 Registro de Blueprints
# =========================================================

app.register_blueprint(chat_bp)
app.register_blueprint(time_bp)
app.register_blueprint(auth_udg_bp, url_prefix='/auth')

# =========================================================
# 🏠 Rutas principales
# =========================================================

@app.route('/')
def index():
    user_id = flask_session.get('user_id')

    if not user_id:
        # Vista GET del login
        return redirect(url_for('auth_udg_bp.login_view'))

    user = User.query.get(user_id)
    if not user:
        flask_session.clear()
        return redirect(url_for('auth_udg_bp.login_view'))

    # Si todo bien, muestra el chat (o tu página principal)
    return render_template('index.html', user=user)



@app.route('/favicon.ico')
def favicon():
    """Evita error 404 del favicon en algunos navegadores."""
    return '', 204

# =========================================================
# ▶️ Ejecución directa
# =========================================================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Crea todas las tablas si no existen

    # Inicia el hilo de escucha multicast (para mensajes entrantes)
    start_listener_thread(app)

    # Corre el servidor Flask
    app.run(host='0.0.0.0', port=5000, debug=True)