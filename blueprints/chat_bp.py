# flask_microservice/blueprints/chat_bp.py
import threading
import queue
import socket
import struct
import time
from flask import Blueprint, Response, request, jsonify, current_app
from config import MULTICAST_GROUP, MULTICAST_PORT

chat_bp = Blueprint('chat_bp', __name__, url_prefix='/chat')

# Cola de mensajes recibidos (FIFO) para SSE
message_queue = queue.Queue()

# Socket multicast (creado y usado en thread)
def create_multicast_listener(group=MULTICAST_GROUP, port=MULTICAST_PORT):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # bind a '' para recibir paquetes dirigidos al puerto
    sock.bind(('', port))
    mreq = struct.pack("4sl", socket.inet_aton(group), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    return sock

def multicast_sender(message, group=MULTICAST_GROUP, port=MULTICAST_PORT):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    # TTL pequeño: 1 => solo LAN local
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, struct.pack('b', 1))
    sock.sendto(message.encode('utf-8'), (group, port))
    sock.close()

def listener_loop():
    sock = create_multicast_listener()
    while True:
        try:
            data, addr = sock.recvfrom(2048)
            texto = data.decode('utf-8')
            # ponemos en la cola para SSE
            message_queue.put(texto)
        except Exception as e:
            # si hay un error grave, esperar y continuar
            current_app.logger.exception("Error listener multicast: %s", e)
            time.sleep(1)

# iniciar thread listener al importar blueprint (solo si no iniciado)
_listener_started = False
def start_listener_thread(app):
    global _listener_started
    if _listener_started:
        return
    _listener_started = True
    t = threading.Thread(target=listener_loop, daemon=True)
    t.start()

# @chat_bp.before_app_first_request
# def ensure_listener_running():
#     start_listener_thread(current_app)

# SSE stream endpoint
def sse_format(event_id, data):
    # simple Server-Sent Event format
    msg = ''
    if event_id is not None:
        msg += f"id: {event_id}\n"
    msg += f"data: {data}\n\n"
    return msg

@chat_bp.route('/stream')
def stream():
    def event_stream():
        # Event ID incremental simple
        event_id = 0
        # enviamos un comment para que el browser mantenga vivo
        yield ": connected\n\n"
        while True:
            try:
                # bloquea hasta que haya mensaje
                texto = message_queue.get()
                event_id += 1
                yield sse_format(event_id, texto)
            except GeneratorExit:
                break
            except Exception as e:
                current_app.logger.exception("Error SSE: %s", e)
                time.sleep(0.5)
    headers = {"Content-Type": "text/event-stream", "Cache-Control": "no-cache", "Connection": "keep-alive"}
    return Response(event_stream(), headers=headers)

# Endpoint para enviar mensajes (desde cliente web o CLI)
@chat_bp.route('/send', methods=['POST'])
def send():
    content = request.json or {}
    message = content.get('message')
    if not message:
        return jsonify({'error': 'Falta campo "message"'}), 400
    try:
        multicast_sender(message)
        # También ponemos localmente para que el emisor lo vea inmediatamente
        message_queue.put(message)
        return jsonify({'status': 'ok'}), 200
    except Exception as e:
        current_app.logger.exception("Error al enviar multicast: %s", e)
        return jsonify({'error': 'no se pudo enviar'}), 500
