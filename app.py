# flask_microservice/app.py
from flask import Flask, render_template
from flask_cors import CORS
from blueprints.time_bp import time_bp
from blueprints.chat_bp import chat_bp, start_listener_thread

def create_app():
    app = Flask(__name__, template_folder='templates', static_folder='static')
    CORS(app, resources={r"/*": {"origins": "*"}})
    app.register_blueprint(time_bp)
    app.register_blueprint(chat_bp)

    # 🔹 Inicia el hilo del listener multicast al arrancar la app
    with app.app_context():
        start_listener_thread(app)

    @app.route('/')
    def index():
        return render_template('index.html')

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, threaded=True)
