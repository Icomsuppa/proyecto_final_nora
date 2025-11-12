# =========================================================
# chat_bp.py — Módulo de Chat (Flask + Multicast)
# =========================================================

# --- Importaciones ---
import os
import json
import time
import uuid
import base64
import queue
import socket
import struct
import threading
from flask import Blueprint, Response, request, jsonify, current_app, send_from_directory, render_template, session as flask_session, redirect, url_for  # ✅ Ya tienes los imports
from models import User

# =========================================================
# Configuración general
# =========================================================

chat_bp = Blueprint('chat_bp', __name__, url_prefix='/chat')

# Carpeta temporal para subir imágenes
TEMP_UPLOAD_FOLDER = 'temp_uploads'
os.makedirs(TEMP_UPLOAD_FOLDER, exist_ok=True)

# Cola global de mensajes SSE
message_queue = queue.Queue()

# =========================================================
# Funciones auxiliares (Multicast)
# =========================================================

def create_multicast_listener(group=None, port=None):
    # obtener valores por defecto desde app config si no se pasan
    group = group or current_app.config.get('MULTICAST_GROUP')
    port = port or int(current_app.config.get('MULTICAST_PORT'))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', port))
    mreq = struct.pack("4sl", socket.inet_aton(group), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    return sock

def multicast_sender(message, group=None, port=None):
    group = group or current_app.config.get('MULTICAST_GROUP')
    port = port or int(current_app.config.get('MULTICAST_PORT'))
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, struct.pack('b', 1))
    sock.sendto(message.encode('utf-8'), (group, port))
    sock.close()

# =========================================================
# Hilo de escucha de mensajes (Listener)
# =========================================================
def listener_loop(app):
    """Escucha mensajes multicast y los agrega a la cola."""
    with app.app_context():
        sock = create_multicast_listener()
        while True:
            try:
                data, addr = sock.recvfrom(2048)
                sender_ip = addr[0]
                try:
                    payload = json.loads(data.decode('utf-8'))
                except json.JSONDecodeError:
                    current_app.logger.warning(f"Mensaje no JSON de {sender_ip}")
                    continue

                payload['sender_ip'] = sender_ip
                message_queue.put(json.dumps(payload))

            except Exception as e:
                current_app.logger.exception(f"Error listener multicast: {e}")
                time.sleep(1)

_listener_started = False

def start_listener_thread(app):
    """Inicia el hilo del listener multicast solo una vez."""
    global _listener_started
    if _listener_started:
        return
    _listener_started = True
    t = threading.Thread(target=listener_loop, args=(app,), daemon=True)
    t.start()


# =========================================================
# Formato de eventos SSE
# =========================================================

def sse_format(event_id, data):
    msg = ''
    if event_id is not None:
        msg += f"id: {event_id}\n"
    msg += f"data: {data}\n\n"
    return msg

# =========================================================
# Rutas del Blueprint
# =========================================================

# --- Ruta: PRINCIPAL ---
@chat_bp.route('/')
def chat_view():
    user_id = flask_session.get('user_id')
    if not user_id:
        return redirect(url_for('auth_udg_bp.login_view')) 

    user = User.query.get(user_id)
    if not user:
        flask_session.clear()
        return redirect(url_for('auth_udg_bp.login_view'))
    
    return render_template('index.html', user=user)  


# --- Ruta: Stream SSE ---
@chat_bp.route('/stream')
def stream():
    """Envía mensajes en tiempo real mediante Server-Sent Events."""
    def event_stream():
        event_id = 0
        yield ": connected\n\n"
        while True:
            try:
                data = message_queue.get()
                event_id += 1
                yield sse_format(event_id, data)
            except GeneratorExit:
                break
            except Exception as e:
                current_app.logger.exception(f"Error SSE: {e}")
                time.sleep(0.5)

    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive"
    }
    return Response(event_stream(), headers=headers)


# --- Ruta: Enviar mensaje ---
@chat_bp.route('/send', methods=['POST'])
def send():
    """Envía un mensaje de texto a todos los usuarios conectados."""
    content = request.json or {}
    if content.get('type') != 'chat':
        return jsonify({'error': 'Tipo de mensaje incorrecto, usa /upload_image para fotos'}), 400

    message = content.get('message')
    user = content.get('user', 'Anon')

    if not message:
        return jsonify({'error': 'Falta campo "message"'}), 400

    payload = {"type": "chat", "user": user, "text": message}

    try:
        multicast_sender(json.dumps(payload))
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        current_app.logger.exception(f"Error al enviar mensaje multicast: {e}")
        return jsonify({'error': 'no se pudo enviar'}), 500


# --- Ruta: Subir imagen ---
@chat_bp.route('/upload_image', methods=['POST'])
def upload_image():
    """Recibe una imagen en base64, la guarda y la transmite por multicast."""
    content = request.json
    if not content or 'image_b64' not in content:
        return jsonify({'error': 'No se recibió imagen (image_b64)'}), 400

    user = content.get('user', 'Anon')
    image_b64 = content.get('image_b64')

    try:
        header, encoded = image_b64.split(',', 1)
        img_data = base64.b64decode(encoded)
        ext = header.split(';')[0].split('/')[1]
        filename = f"{uuid.uuid4()}.{ext}"

        abs_upload_folder = os.path.join(current_app.root_path, TEMP_UPLOAD_FOLDER)
        os.makedirs(abs_upload_folder, exist_ok=True)
        filepath = os.path.join(abs_upload_folder, filename)

        with open(filepath, 'wb') as f:
            f.write(img_data)

        payload = {"type": "image", "user": user, "filename": filename}
        multicast_sender(json.dumps(payload))

        return jsonify({'status': 'ok', 'filename': filename}), 200

    except Exception as e:
        current_app.logger.exception(f"Error al guardar o enviar imagen: {e}")
        return jsonify({'error': 'Error interno al procesar imagen'}), 500


# --- Ruta: Servir imágenes temporales ---
@chat_bp.route('/temp_images/<path:filename>')
def serve_temp_image(filename):
    """Sirve las imágenes subidas temporalmente."""
    try:
        abs_upload_folder = os.path.join(current_app.root_path, TEMP_UPLOAD_FOLDER)
        return send_from_directory(abs_upload_folder, filename, as_attachment=False)
    except FileNotFoundError:
        current_app.logger.error(f"Imagen no encontrada: {filename}")
        return jsonify({'error': 'Imagen no encontrada'}), 404
    except Exception as e:
        current_app.logger.error(f"Error interno al servir imagen: {e}")
        return jsonify({'error': 'Error interno'}), 500