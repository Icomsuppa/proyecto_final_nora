import os
from flask import Flask, render_template, send_from_directory
from blueprints.chat_bp import chat_bp, start_listener_thread
from blueprints.time_bp import time_bp # Asumo que tienes este blueprint

# --- ¡AQUÍ ESTÁ EL ARREGLO! ---

# 1. Define la ruta raíz (donde está este app.py)
root_dir = os.path.dirname(os.path.abspath(__file__))

# 2. (MODIFICADO) Define las rutas a las carpetas 'static' y 'templates'
# ¡Le quitamos 'flask_microservice' porque están en la raíz!
static_dir = os.path.join(root_dir, 'static')
templates_dir = os.path.join(root_dir, 'templates')

# 3. Crea la aplicación Flask... ¡Y LE DICE DÓNDE ESTÁN LAS CARPETAS!
app = Flask(__name__,
            template_folder=templates_dir,
            static_folder=static_dir)

# 4. Registra los blueprints (los módulos de tu app)
app.register_blueprint(chat_bp)
app.register_blueprint(time_bp)

# 5. Define la ruta principal (la que sirve el index.html)
@app.route('/')
def index():
    # Ahora sí encontrará 'index.html' en la carpeta 'templates' correcta
    return render_template('index.html')

# 6. (OPCIONAL) Una ruta para el favicon que da 404
@app.route('/favicon.ico')
def favicon():
    return '', 204

# 7. El bloque para correr la app
if __name__ == '__main__':
    # Inicia el hilo del listener (esto es de chat_bp.py)
    start_listener_thread(app)
    
    # Corre la aplicación
    app.run(host='0.0.0.0', port=5000)