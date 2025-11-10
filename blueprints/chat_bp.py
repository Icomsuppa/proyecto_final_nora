# --- Importaciones de librerías ---

import threading  # Para ejecutar tareas en segundo plano (el listener)
import queue      # Para la cola de mensajes (FIFO, thread-safe)
import socket     # Para la comunicación de red (multicast)
import struct     # Para empaquetar datos binarios (para opciones de socket)
import time       # Para pausas (time.sleep)
from flask import Blueprint, Response, request, jsonify, current_app
# Blueprint: para modularizar la app Flask
# Response: para crear la respuesta de streaming (SSE)
# request: para acceder a los datos de la solicitud (JSON)
# jsonify: para crear respuestas JSON
# current_app: para acceder a la app Flask actual (ej. para logs)
from config import MULTICAST_GROUP, MULTICAST_PORT # Importa la IP y puerto del config

# --- Configuración del Blueprint ---

# Crea un Blueprint llamado 'chat_bp'.
# Todas las rutas definidas aquí tendrán el prefijo '/chat'.
chat_bp = Blueprint('chat_bp', __name__, url_prefix='/chat')

# --- Globales del Módulo ---

# Crea una cola FIFO (First-In, First-Out) para los mensajes.
# Es 'thread-safe', lo que significa que se puede usar desde
# el hilo del listener y los hilos de Flask sin conflictos.
message_queue = queue.Queue()

# --- Funciones de Multicast ---

# Socket multicast (creado y usado en thread)
def create_multicast_listener(group=MULTICAST_GROUP, port=MULTICAST_PORT):
    """Configura y devuelve un socket para escuchar mensajes multicast."""
    
    # Crea un socket: AF_INET (IPv4), SOCK_DGRAM (UDP)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    
    # Permite que el socket reutilice la dirección (evita errores al reiniciar)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # Vincula el socket a todas las interfaces ('') en el puerto especificado.
    # Esto es necesario para RECIBIR paquetes.
    sock.bind(('', port))
    
    # Prepara la solicitud de membresía al grupo multicast.
    # Empaqueta la IP del grupo y la IP de la interfaz (INADDR_ANY = cualquiera)
    mreq = struct.pack("4sl", socket.inet_aton(group), socket.INADDR_ANY)
    
    # Le dice al kernel que este socket se une al grupo multicast.
    # El sistema operativo ahora reenviará paquetes de este grupo al socket.
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    
    return sock

def multicast_sender(message, group=MULTICAST_GROUP, port=MULTICAST_PORT):
    """Envía un mensaje a través de multicast."""
    
    # Crea un socket UDP para enviar
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    
    # Configura el 'Time To Live' (TTL) del paquete.
    # 1 significa que solo viajará en la red local (no cruzará routers).
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, struct.pack('b', 1))
    
    # Envía el mensaje (codificado en utf-8) al grupo y puerto multicast.
    sock.sendto(message.encode('utf-8'), (group, port))
    
    # Cierra el socket de envío (es de corta duración).
    sock.close()

# --- Hilo del Listener Multicast ---

def listener_loop():
    """Bucle infinito que escucha mensajes multicast y los pone en la cola."""
    
    # Crea el socket de escucha una vez.
    sock = create_multicast_listener()
    
    # Bucle infinito para escuchar continuamente.
    while True:
        try:
            # Espera (bloquea) hasta recibir un paquete (máx 2048 bytes).
            data, addr = sock.recvfrom(2048)
            
            # Decodifica los bytes recibidos a un string utf-8.
            texto = data.decode('utf-8')
            
            # Pone el mensaje de texto en la cola para que el SSE lo recoja.
            message_queue.put(texto)
            
        except Exception as e:
            # Si hay un error grave (ej. de red), lo registra.
            current_app.logger.exception("Error listener multicast: %s", e)
            # Espera 1 segundo antes de reintentar para evitar spam de logs.
            time.sleep(1)

# --- Arranque del Hilo ---

# Bandera global para asegurar que el hilo se inicie solo una vez.
_listener_started = False

def start_listener_thread(app):
    """Inicia el hilo del listener_loop si no se ha iniciado ya."""
    
    global _listener_started
    
    # Si el hilo ya está corriendo, no hace nada.
    if _listener_started:
        return
        
    # Marca el hilo como iniciado.
    _listener_started = True
    
    # Crea el hilo.
    # target=listener_loop: la función que ejecutará el hilo.
    # daemon=True: el hilo morirá automáticamente cuando el proceso principal (Flask) muera.
    t = threading.Thread(target=listener_loop, daemon=True)
    
    # Inicia la ejecución del hilo.
    t.start()

# Esta es la forma antigua (y deprecada) de ejecutar código antes de la primera solicitud.
# @chat_bp.before_app_first_request
# def ensure_listener_running():
#     start_listener_thread(current_app)

# --- Endpoints HTTP (Rutas) ---

def sse_format(event_id, data):
    """Formatea un string según la especificación de Server-Sent Events (SSE)."""
    
    # Formato SSE simple.
    msg = ''
    
    # Agrega un ID al evento (opcional pero recomendado).
    if event_id is not None:
        msg += f"id: {event_id}\n"
        
    # El contenido del mensaje va en el campo 'data:'.
    msg += f"data: {data}\n\n" # El doble salto de línea (\n\n) es obligatorio.
    
    return msg

@chat_bp.route('/stream')
def stream():
    """Endpoint de streaming (SSE) que envía mensajes desde la cola al cliente."""
    
    def event_stream():
        """Un generador que produce eventos SSE."""
        
        # Un ID simple que se incrementa por cada mensaje.
        event_id = 0
        
        # Envía un "comentario" SSE. Esto confirma la conexión
        # y puede usarse como un 'keep-alive'.
        yield ": connected\n\n"
        
        # Bucle infinito para enviar mensajes mientras el cliente esté conectado.
        while True:
            try:
                # Intenta obtener un mensaje de la cola.
                # Esta llamada .get() es bloqueante: pausa el hilo
                # hasta que haya un mensaje disponible.
                texto = message_queue.get()
                
                # Incrementa el ID del evento.
                event_id += 1
                
                # Envía (yield) el mensaje formateado como SSE.
                yield sse_format(event_id, texto)
                
            except GeneratorExit:
                # Esta excepción ocurre si el cliente (navegador) cierra la conexión.
                # Se rompe el bucle para limpiar el generador.
                break
                
            except Exception as e:
                # Captura cualquier otro error durante el streaming.
                current_app.logger.exception("Error SSE: %s", e)
                # Pausa brevemente antes de continuar.
                time.sleep(0.5)
                
    # Define las cabeceras HTTP necesarias para SSE.
    headers = {
        "Content-Type": "text/event-stream", # Tipo de contenido clave para SSE
        "Cache-Control": "no-cache",         # Evita que el navegador cachee la respuesta
        "Connection": "keep-alive"           # Mantiene la conexión abierta
    }
    
    # Devuelve un objeto Response de Flask.
    # Pasa el generador (event_stream()) y las cabeceras.
    # Flask se encargará de streamear la salida del generador.
    return Response(event_stream(), headers=headers)

@chat_bp.route('/send', methods=['POST'])
def send():
    """Endpoint para que un cliente envíe un mensaje (vía POST JSON)."""
    
    # Obtiene el cuerpo de la solicitud como JSON. Si no hay JSON, usa un dict vacío.
    content = request.json or {}
    
    # Extrae el valor del campo 'message'.
    message = content.get('message')
    
    # Valida que el mensaje exista.
    if not message:
        # Devuelve un error 400 (Bad Request) si falta el mensaje.
        return jsonify({'error': 'Falta campo "message"'}), 400
        
    try:
        # 1. Envía el mensaje a la red multicast.
        #    Esto lo recibirán todas las *otras* instancias de la app.
        multicast_sender(message)
        
        # 2. También pone el mensaje en la cola local.
        #    Esto es para que el *propio emisor* vea su mensaje
        #    inmediatamente en su stream SSE.
        message_queue.put(message)
        
        # Devuelve un 200 (OK) si todo fue bien.
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        # Si falla el envío (ej. error de red), lo registra.
        current_app.logger.exception("Error al enviar multicast: %s", e)
        # Devuelve un error 500 (Internal Server Error).
        return jsonify({'error': 'no se pudo enviar'}), 500