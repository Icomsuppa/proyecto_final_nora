# =========================================================
<<<<<<< HEAD
# chat_bp.py — Módulo de Chat (Flask + Multicast)
=======
#  chat_bp.py — Módulo de Chat (Flask + Multicast)
>>>>>>> 46a3d7a0eeddf327009ba9cc4c7812bad49bcf6a
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
<<<<<<< HEAD
# Configuración general
=======
#  Configuración general
>>>>>>> 46a3d7a0eeddf327009ba9cc4c7812bad49bcf6a
# =========================================================

chat_bp = Blueprint('chat_bp', __name__, url_prefix='/chat')

# Carpeta temporal para subir imágenes
TEMP_UPLOAD_FOLDER = 'temp_uploads'
os.makedirs(TEMP_UPLOAD_FOLDER, exist_ok=True)

# Cola global de mensajes SSE
message_queue = queue.Queue()

# =========================================================
<<<<<<< HEAD
# Funciones auxiliares (Multicast)
=======
#  Funciones auxiliares (Multicast)
>>>>>>> 46a3d7a0eeddf327009ba9cc4c7812bad49bcf6a
# =========================================================

# Define la función para crear el "oído" (listener)
def create_multicast_listener(group=None, port=None):
    # Pone el grupo de la config si no se pasa uno
    group = group or current_app.config.get('MULTICAST_GROUP')
    # Pone el puerto de la config si no se pasa uno
    port = port or int(current_app.config.get('MULTICAST_PORT'))
    # Crea un socket UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    # Permite que varios usen el mismo puerto
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # Se amarra al puerto para escuchar
    sock.bind(('', port))
    # Prepara la solicitud para unirse al grupo
    mreq = struct.pack("4sl", socket.inet_aton(group), socket.INADDR_ANY)
    # Le dice al sistema "quiero unirme a este grupo"
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    # Regresa el "oído" listo
    return sock

# Define la función para "gritar" (enviar) el mensaje
def multicast_sender(message, group=None, port=None):
    # Pone el grupo de la config si no se pasa uno
    group = group or current_app.config.get('MULTICAST_GROUP')
    # Pone el puerto de la config si no se pasa uno
    port = port or int(current_app.config.get('MULTICAST_PORT'))
    # Crea un socket UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    # Limita el mensaje a la red local (que no se vaya a internet)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, struct.pack('b', 1))
    # Envía el mensaje (en bytes) al grupo y puerto
    sock.sendto(message.encode('utf-8'), (group, port))
    # Cierra el socket
    sock.close()

# =========================================================
# Hilo de escucha de mensajes (Listener)
# =========================================================

# Esta es la función que correrá en un hilo (thread) separado
# para escuchar mensajes sin bloquear la aplicación principal de Flask.
def listener_loop(app):
    """Escucha mensajes multicast y los agrega a la cola."""
    
    # 'app.app_context()' es necesario porque este hilo corre fuera del
    # contexto normal de Flask. Esto le da acceso a 'current_app' (para logs)
    # y otras configuraciones de la aplicación.
    with app.app_context():
        # Llama a la función que crea y configura el socket de escucha multicast
        sock = create_multicast_listener()
        
        # Bucle infinito para que el hilo siempre esté escuchando.
        while True:
            try:
                # Espera (bloquea) hasta que llegue un paquete de datos (máx 2048 bytes).
                # 'data' son los bytes recibidos, 'addr' es una tupla (ip, puerto) del remitente.
                data, addr = sock.recvfrom(2048)
                # Extrae solo la dirección IP del remitente.
                sender_ip = addr[0]

                # Intenta procesar los datos recibidos.
                try:
                    # Decodifica los bytes a un string (utf-8) y luego
                    # convierte (parsea) ese string JSON a un diccionario de Python.
                    payload = json.loads(data.decode('utf-8'))
                except json.JSONDecodeError:
                    # Si los datos no son un JSON válido, avisa en el log.
                    current_app.logger.warning(f"Mensaje no JSON de {sender_ip}")
                    # 'continue' salta al inicio del 'while' para esperar el próximo mensaje.
                    continue

                # Agrega la IP del remitente al diccionario (payload) que se recibió.
                payload['sender_ip'] = sender_ip
                
                # Convierte el diccionario de Python (ya con la IP) de nuevo a un string JSON
                # y lo pone en la 'message_queue'.
                # La ruta '/stream' (SSE) está sacando mensajes de esta cola.
                message_queue.put(json.dumps(payload))

            except Exception as e:
                # Captura cualquier otro error (ej. problema de red).
                current_app.logger.exception(f"Error listener multicast: {e}")
                # Espera 1 segundo antes de reintentar para no saturar la CPU
                # en caso de un error persistente.
                time.sleep(1)


# Esta es una flag global para 
# que escuche solo se inicie una vez.
_listener_started = False

def start_listener_thread(app):
    """Inicia el hilo del listener multicast solo una vez."""
    
    # Indica que queremos usar la variable global '_listener_started'
    # y no crear una nueva variable local con el mismo nombre.
    global _listener_started
    
    # Revisa si la bandera ya está en 'True'.
    if _listener_started:
        # Si es así, el hilo ya está corriendo.
        return
        
    # Si no estaba iniciada, marcamos la bandera como 'True' 
    _listener_started = True
    
    # Crea el objeto Hilo (Thread).
    # 'target=listener_loop': La función que el hilo va a ejecutar.
    # 'args=(app,)': Los argumentos que se le pasarán a 'listener_loop'.
    # 'daemon=True': Importante. Significa que el hilo se cerrará automáticamente
    # cuando el programa principal (Flask) termine.
    t = threading.Thread(target=listener_loop, args=(app,), daemon=True)
    
    # Inicia el hilo. 'listener_loop' empezará a ejecutarse en segundo plano.
    t.start()

# =========================================================
<<<<<<< HEAD
# Formato de eventos SSE
=======
#  Formato de eventos SSE
>>>>>>> 46a3d7a0eeddf327009ba9cc4c7812bad49bcf6a
# =========================================================

# Define una función simple para dar formato a los datos según el estándar SSE.
def sse_format(event_id, data):
    # Inicializa una cadena vacía para construir el mensaje.
    msg = ''
    
    # Si se proporciona un 'event_id' (que no sea None)...
    if event_id is not None:
        # Agrega la línea 'id:' al mensaje. Esto ayuda al cliente a rastrear el último evento recibido.
        msg += f"id: {event_id}\n"
        
    # Agrega la línea 'data:'. Aquí es donde van los datos reales (el payload JSON).
    # '\n\n' (dos saltos de línea) es crucial, indica el final del evento.
    msg += f"data: {data}\n\n"
    
    # Devuelve la cadena de texto formateada.
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

# Define la ruta '/stream'. Esta es la que el cliente (navegador) usará para conectarse.
@chat_bp.route('/stream')
def stream():
    """Envía mensajes en tiempo real mediante Server-Sent Events."""
    
    # Define una función 'generadora'. Esta función no se ejecuta toda de golpe,
    # sino que se pausa en cada 'yield' y mantiene la conexión abierta.
    def event_stream():
        # Inicializa un contador para el ID de cada evento.
        event_id = 0
        
        # Envía un mensaje inicial solo para confirmar la conexión al cliente.
        # El formato ": <comentario>\n\n" es un comentario SSE que el cliente ignora.
        yield ": connected\n\n"
        
        # Bucle infinito: mantiene la conexión abierta y escuchando mensajes.
        while True:
            try:
                # Intenta obtener un mensaje de la cola ('message_queue').
                # Esta cola (queue) debe estar definida en otro lado y es donde
                # el 'multicast_sender' de las otras rutas pone los mensajes.
                # .get() es bloqueante: espera hasta que haya un mensaje.
                data = message_queue.get()
                
                # Incrementa el ID del evento.
                event_id += 1
                
                # 'yield' envía los datos al cliente.
                # Llama a 'sse_format' (otra función que debes tener) para
                # formatear los datos 'data' en el estándar SSE
                yield sse_format(event_id, data)
                
            except GeneratorExit:
                # Esto ocurre si el cliente (navegador) cierra la conexión.
                # 'break' rompe el bucle 'while True' y termina la función generadora.
                break
                
            except Exception as e:
                # Captura cualquier otro error que ocurra dentro del bucle.
                current_app.logger.exception(f"Error SSE: {e}")
                # Espera un momento antes de reintentar para no saturar la CPU
                time.sleep(0.5)

    # Estos encabezados (headers) son cruciales para que SSE funcione.
    headers = {
        # Le dice al navegador que esto es un flujo de eventos.
        "Content-Type": "text/event-stream",
        # Evita que el navegador o un proxy guarden en caché la respuesta.
        "Cache-Control": "no-cache",
        # Indica que la conexión debe permanecer abierta.
        "Connection": "keep-alive"
    }
    
    # Crea una respuesta de Flask.
    # Pasa la función generadora 'event_stream()' como el cuerpo de la respuesta.
    # Flask ejecutará esta función y enviará cada 'yield' al cliente.
    # También aplica los encabezados SSE definidos arriba.
    return Response(event_stream(), headers=headers)


# --- Ruta: Enviar mensaje ---

# Define una ruta en '/send' que solo acepta peticiones POST.
@chat_bp.route('/send', methods=['POST'])
def send():
    """Envía un mensaje de texto a todos los usuarios conectados."""
    
    # Obtiene los datos JSON de la petición. Si no hay JSON, usa un diccionario vacío.
    content = request.json or {}
    
    # Comprueba que el tipo de contenido sea 'chat'.
    # Si intentan mandar otra cosa (como una imagen por aquí), les dice que usen la otra ruta.
    if content.get('type') != 'chat':
        return jsonify({'error': 'Tipo de mensaje incorrecto, usa /upload_image para fotos'}), 400

    # Saca el mensaje del JSON.
    message = content.get('message')
    # Saca el nombre de usuario. Si no viene, lo llama 'Anon'.
    user = content.get('user', 'Anon')

    # Valida que el campo 'message' no esté vacío o falte.
    if not message:
        return jsonify({'error': 'Falta campo "message"'}), 400

    # Prepara el paquete de datos (payload) que se va a enviar.
    payload = {"type": "chat", "user": user, "text": message}

    try:
        # Intenta enviar el payload (convertido a JSON) usando la función multicast.
        multicast_sender(json.dumps(payload))
        
        # Si todo sale bien, regresa un 'ok'.
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        # Si algo truena al enviar (ej. la red falla), captura el error.
        # Lo guarda en el log de la app.
        current_app.logger.exception(f"Error al enviar mensaje multicast: {e}")
        # Avisa al cliente que no se pudo enviar.
        return jsonify({'error': 'no se pudo enviar'}), 500


# --- Ruta: Subir imagen ---

# Define una ruta en el Blueprint que escucha en '/upload_image'.
# Solo acepta peticiones HTTP de tipo POST.
@chat_bp.route('/upload_image', methods=['POST'])
def upload_image():
    """Recibe una imagen en base64, la guarda y la transmite por multicast."""
    
    # Obtiene los datos JSON que vienen en la petición POST.
    content = request.json
    
    # Valida si se recibieron datos JSON y si la llave 'image_b64' existe.
    if not content or 'image_b64' not in content:
        # Si no hay imagen, regresa un error 400 (Bad Request).
        return jsonify({'error': 'No se recibió imagen (image_b64)'}), 400

    # Obtiene el nombre de 'user' del JSON, o usa 'Anon' si no viene.
    user = content.get('user', 'Anon')
    # Obtiene la cadena de la imagen en base64.
    image_b64 = content.get('image_b64')

    try:
        # La cadena base64 usualmente viene como "data:image/png;base64,ENCODED_DATA".
        header, encoded = image_b64.split(',', 1)
        
        # Decodifica la cadena base64 a bytes de imagen.
        img_data = base64.b64decode(encoded)
        
        # Extrae la extensión del archivo (ej. 'png') del encabezado.
        ext = header.split(';')[0].split('/')[1]
        
        # Genera un nombre de archivo único usando UUID para evitar colisiones.
        filename = f"{uuid.uuid4()}.{ext}"

        # Define la ruta absoluta de la carpeta donde se guardará la imagen.
        abs_upload_folder = os.path.join(current_app.root_path, TEMP_UPLOAD_FOLDER)
        # Crea la carpeta si no existe.
        os.makedirs(abs_upload_folder, exist_ok=True)
        # Crea la ruta completa del archivo (carpeta + nombre de archivo).
        filepath = os.path.join(abs_upload_folder, filename)

        # Abre el archivo en modo "write binary" (escritura binaria).
        with open(filepath, 'wb') as f:
            # Escribe los bytes de la imagen en el archivo.
            f.write(img_data)

        # Prepara un 'payload' (datos) en formato JSON para enviar por multicast.
        payload = {"type": "image", "user": user, "filename": filename}
        # Llama a la función que envía el mensaje por multicast (esta debe estar definida en otra parte).
        multicast_sender(json.dumps(payload))

        # Regresa una respuesta de éxito (200) con el nombre del archivo guardado.
        return jsonify({'status': 'ok', 'filename': filename}), 200

    except Exception as e:
        # Si algo falla en el bloque 'try' (ej. base64 malformado, error al escribir), se captura aquí.
        # Registra el error en el log de la aplicación.
        current_app.logger.exception(f"Error al guardar o enviar imagen: {e}")
        # Regresa un error genérico 500 (Internal Server Error).
        return jsonify({'error': 'Error interno al procesar imagen'}), 500

# --- Ruta: Servir imágenes temporales ---

# Define una ruta que escucha en '/temp_images/' seguido de un nombre de archivo.
# El '<path:filename>' permite que 'filename' incluya subdirectorios (aunque aquí no se usa).
@chat_bp.route('/temp_images/<path:filename>')
def serve_temp_image(filename):
    """Sirve las imágenes subidas temporalmente."""
    
    try:
        # Calcula la ruta absoluta de la carpeta donde están las imágenes.
        abs_upload_folder = os.path.join(current_app.root_path, TEMP_UPLOAD_FOLDER)
        
        # Usa una función de Flask ('send_from_directory') para enviar el archivo de forma segura.
        # Busca 'filename' dentro de 'abs_upload_folder'.
        # 'as_attachment=False' hace que el navegador muestre la imagen en lugar de descargarla.
        return send_from_directory(abs_upload_folder, filename, as_attachment=False)
        
    except FileNotFoundError:
        # Si 'send_from_directory' no encuentra el archivo, captura el error.
        current_app.logger.error(f"Imagen no encontrada: {filename}")
        # Devuelve un error 404 (Not Found).
        return jsonify({'error': 'Imagen no encontrada'}), 404
        
    except Exception as e:
        # Captura cualquier otro error inesperado (ej. problemas de permisos).
        current_app.logger.error(f"Error interno al servir imagen: {e}")
<<<<<<< HEAD
=======
        # Devuelve un error 500 (Internal Server Error).
>>>>>>> 46a3d7a0eeddf327009ba9cc4c7812bad49bcf6a
        return jsonify({'error': 'Error interno'}), 500