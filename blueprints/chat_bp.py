# --- Importaciones de librerías ---

import threading
import queue
import socket
import struct
import time
import json
import os
import uuid
import base64
from flask import Blueprint, Response, request, jsonify, current_app, send_from_directory
from config import MULTICAST_GROUP, MULTICAST_PORT

# --- Configuración del Blueprint ---
chat_bp = Blueprint('chat_bp', __name__, url_prefix='/chat')

# --- Globales del Módulo ---
message_queue = queue.Queue()

# --- (MODIFICADO) ¡AQUÍ ESTÁ EL ARREGLO DE RUTA! ---
# La carpeta ahora se creará en la raíz (proyecto_final_nora/temp_uploads)
TEMP_UPLOAD_FOLDER_REL = 'temp_uploads'
os.makedirs(TEMP_UPLOAD_FOLDER_REL, exist_ok=True)


# --- Funciones de Multicast (SIN CAMBIOS) ---
def create_multicast_listener(group=MULTICAST_GROUP, port=MULTICAST_PORT):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(('', port))
    mreq = struct.pack("4sl", socket.inet_aton(group), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    return sock

def multicast_sender(message, group=MULTICAST_GROUP, port=MULTICAST_PORT):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, struct.pack('b', 1))
    sock.sendto(message.encode('utf-8'), (group, port))
    sock.close()

# --- Hilo del Listener Multicast (SIN CAMBIOS) ---
def listener_loop():
    sock = create_multicast_listener()
    while True:
        try:
            data, addr = sock.recvfrom(2048) 
            sender_ip = addr[0]
            texto_json_str = data.decode('utf-8')
            
            try:
                payload = json.loads(texto_json_str)
            except json.JSONDecodeError:
                current_app.logger.warning(f"Recibido mensaje no-JSON de {sender_ip}")
                continue 

            payload['sender_ip'] = sender_ip
            message_queue.put(json.dumps(payload))
            
        except Exception as e:
            current_app.logger.exception("Error listener multicast: %s", e)
            time.sleep(1)

# --- Arranque del Hilo (SIN CAMBIOS) ---
_listener_started = False
def start_listener_thread(app):
    global _listener_started
    if _listener_started:
        return
    _listener_started = True
    t = threading.Thread(target=listener_loop, daemon=True)
    t.start()

# --- Endpoints HTTP (Rutas) ---

# --- Ruta /stream y sse_format (SIN CAMBIOS) ---
def sse_format(event_id, data):
    msg = ''
    if event_id is not None:
        msg += f"id: {event_id}\n"
    msg += f"data: {data}\n\n"
    return msg

@chat_bp.route('/stream')
def stream():
    def event_stream():
        event_id = 0
        yield ": connected\n\n"
        while True:
            try:
                texto_json_enriquecido = message_queue.get()
                event_id += 1
                yield sse_format(event_id, texto_json_enriquecido)
            except GeneratorExit:
                break
            except Exception as e:
                current_app.logger.exception("Error SSE: %s", e)
                time.sleep(0.5)
    headers = {"Content-Type": "text/event-stream", "Cache-Control": "no-cache", "Connection": "keep-alive"}
    return Response(event_stream(), headers=headers)

# --- Ruta /send (SIN CAMBIOS) ---
@chat_bp.route('/send', methods=['POST'])
def send():
    content = request.json or {}
    if content.get('type') != 'chat':
        return jsonify({'error': 'Tipo de mensaje incorrecto, usa /upload_image para fotos'}), 400

    message = content.get('message') 
    user = content.get('user', 'Anon') 
    
    if not message:
        return jsonify({'error': 'Falta campo "message"'}), 400
        
    payload = {
        "type": "chat",
        "user": user,
        "text": message
    }
    payload_str = json.dumps(payload)

    try:
        multicast_sender(payload_str)
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        current_app.logger.exception("Error al enviar multicast: %s", e)
        return jsonify({'error': 'no se pudo enviar'}), 500


# --- (MODIFICADO) ¡AQUÍ ESTÁ EL ARREGLO DE RUTA! ---
@chat_bp.route('/upload_image', methods=['POST'])
def upload_image():
    content = request.json
    if not content or 'image_b64' not in content:
        return jsonify({'error': 'No se recibió imagen (image_b64)'}), 400

    user = content.get('user', 'Anon')
    image_b64 = content.get('image_b64')

    try:
        try:
            header, encoded = image_b64.split(',', 1)
            img_data = base64.b64decode(encoded)
        except Exception as e:
            current_app.logger.error(f"Error decodificando Base64: {e}")
            return jsonify({'error': 'Formato Base64 inválido'}), 400

        ext = header.split(';')[0].split('/')[1]
        filename = f"{uuid.uuid4()}.{ext}"

        # --- ¡EL ARREGLO! ---
        # Construimos la RUTA ABSOLUTA usando la raíz de la app (donde está app.py)
        abs_upload_folder = os.path.join(current_app.root_path, TEMP_UPLOAD_FOLDER_REL)
        
        # Nos aseguramos de que la ruta absoluta exista
        os.makedirs(abs_upload_folder, exist_ok=True) 
        
        # Usamos la ruta absoluta para guardar
        filepath = os.path.join(abs_upload_folder, filename)

        with open(filepath, 'wb') as f:
            f.write(img_data)

        notification_payload = {
            "type": "image",
            "user": user,
            "filename": filename 
        }
        
        multicast_sender(json.dumps(notification_payload))
        return jsonify({'status': 'ok', 'filename': filename}), 200

    except Exception as e:
        current_app.logger.exception("Error al guardar o notificar imagen: %s", e)
        return jsonify({'error': 'Error interno al procesar imagen'}), 500


# --- (MODIFICADO) ¡AQUÍ ESTÁ EL ARREGLO DE RUTA! ---
@chat_bp.route('/temp_images/<path:filename>')
def serve_temp_image(filename):
    """Sirve los archivos de imagen guardados en la carpeta absoluta."""
    
    try:
        # Construimos la RUTA ABSOLUTA de nuevo para que sepa dónde buscar
        abs_upload_folder = os.path.join(current_app.root_path, TEMP_UPLOAD_FOLDER_REL)

        return send_from_directory(
            abs_upload_folder, 
            filename,
            as_attachment=False 
        )
    except FileNotFoundError:
        current_app.logger.error(f"404 - No se encontró la imagen: {filename} en {abs_upload_folder}")
        return jsonify({'error': 'Imagen no encontrada'}), 404
    except Exception as e:
        current_app.logger.error(f"Error raro en serve_temp_image: {e}")
        return jsonify({'error': 'Error interno'}), 500