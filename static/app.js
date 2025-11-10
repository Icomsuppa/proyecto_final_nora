// --- Variables Globales ---

// La conexión al stream de Server-Sent Events (SSE).
// Se inicializa en null para saber que no estamos conectados.
let es = null;

// --- Selección de Elementos del DOM ---

// El <textarea> donde se muestran todos los mensajes del chat.
const messages = document.getElementById('messages');
// El <input> donde el usuario escribe su mensaje.
const input = document.getElementById('input');
// El botón para enviar un mensaje.
const sendBtn = document.getElementById('send');
// El botón para conectarse al stream de chat.
const connectBtn = document.getElementById('btnConnect');
// El <input> donde el usuario pone su nombre.
const usernameInput = document.getElementById('username');
// El botón para obtener la hora del servidor.
const getTimeBtn = document.getElementById('getTime');

// --- Funciones Auxiliares ---

/**
 * Agrega un mensaje de texto al <textarea> 'messages'
 * y se asegura de que la vista se desplace hacia abajo.
 * @param {string} msg - El mensaje a mostrar.
 */
function append(msg) {
    // Agrega el mensaje y un salto de línea.
    messages.textContent += msg + '\n';
    // Mueve el scroll del textarea hasta el final.
    messages.scrollTop = messages.scrollHeight;
}

// --- Lógica de Eventos (Botones) ---

/**
 * Manejador del clic para el botón 'Conectar'.
 * Establece la conexión SSE con el servidor.
 */
connectBtn.onclick = () => {
    // Primero, revisa si ya existe una conexión activa.
    if (es) {
        append('Ya estás conectado al stream.');
        return; // No hace nada más si ya está conectado.
    }

    // Si no hay conexión, crea una nueva.
    append('Conectando al stream SSE...');
    // Crea la instancia de EventSource apuntando a la ruta del servidor.
    es = new EventSource('/chat/stream');
    append('Ya estas Conectado');

    /**
     * Se activa cada vez que el servidor envía un mensaje
     * a través del stream.
     */
    es.onmessage = function (e) {
        // 'e.data' contiene el texto del mensaje enviado por el servidor.
        append(e.data);
    };

    /**
     * Se activa si hay un error en la conexión SSE.
     */
    es.onerror = function (e) {
        append('Error SSE, reintentando...');
        // El navegador intentará reconectar automáticamente por defecto.
    };
};

/**
 * Manejador del clic para el botón 'Enviar'.
 * Envía el mensaje del usuario al servidor usando fetch (POST).
 */
sendBtn.onclick = async () => {
    // Obtiene el nombre de usuario, o usa 'Anon' si está vacío.
    const name = usernameInput.value.trim() || 'Anon';
    // Obtiene el texto del mensaje.
    const text = input.value.trim();

    // No envía nada si el campo de texto está vacío.
    if (!text) return;

    // Prepara el objeto (payload) que se enviará al servidor.
    const payload = { message: `[${new Date().toLocaleTimeString()}] ${name}: ${text}` };

    try {
        // Realiza la solicitud POST al servidor.
        const r = await fetch('/chat/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload) // Convierte el objeto a JSON.
        });

        // Comprueba si el servidor respondió correctamente (ej. 200 OK).
        if (!r.ok) {
            append('Error al enviar mensaje al servidor.');
        } else {
            // Si se envió bien, limpia el campo de texto.
            input.value = '';
        }
    } catch (e) {
        // Captura errores de red (ej. servidor caído).
        append('Error de red al enviar mensaje.');
    }
};

/**
 * Agrega un listener al campo de texto para que la tecla 'Enter'
 * también envíe el mensaje.
 */
input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        sendBtn.click(); // Simula un clic en el botón 'Enviar'.
    }
});

/**
 * Manejador del clic para el botón 'Obtener Hora'.
 * Pide la hora al servidor y la compara con la hora local.
 * Incluye un timeout de 5 segundos.
 */
getTimeBtn.onclick = async () => {
    // AbortController se usa para cancelar el fetch si tarda mucho.
    const controller = new AbortController();
    // Configura un temporizador de 5 segundos (5000 ms).
    const id = setTimeout(() => controller.abort(), 5000);

    try {
        // Inicia el fetch, pasando el 'signal' del AbortController.
        const resp = await fetch('/time/', { signal: controller.signal });
        
        // Si el fetch tuvo éxito, cancela el temporizador de timeout.
        clearTimeout(id);

        // Comprueba si la respuesta del servidor fue exitosa.
        if (!resp.ok) {
            append('Error al pedir hora al servidor');
            return;
        }

        // Parsea la respuesta JSON del servidor.
        const data = await resp.json();
        const serverTimeStr = data.time; // Formato esperado "HH:MM:SS"
        
        // Convierte "HH:MM:SS" a un array de números [HH, MM, SS].
        const serverParts = serverTimeStr.split(':').map(x => parseInt(x, 10));
        
        // Obtiene la fecha y hora local actual.
        const nowLocal = new Date();
        
        // Crea un objeto Date para la hora del servidor, pero usando
        // el AÑO, MES y DÍA de la máquina local. Esto es para
        // comparar solo las horas, minutos y segundos.
        const serverNow = new Date(nowLocal.getFullYear(), nowLocal.getMonth(), nowLocal.getDate(),
            serverParts[0], serverParts[1], serverParts[2]);

        // Calcula la diferencia en milisegundos.
        const diffMs = nowLocal - serverNow;
        // Convierte la diferencia a segundos y la redondea.
        const diffSec = Math.round(diffMs / 1000);

        // Muestra los resultados en el chat.
        append(`Hora servidor: ${data.date} ${data.time}`);
        append(`Hora local: ${nowLocal.toLocaleString()}`);
        
        if (diffSec > 0) {
            append(`La hora local está ${diffSec} segundos ADELANTADA.`);
        } else if (diffSec < 0) {
            append(`La hora local está ${-diffSec} segundos ATRASADA.`);
        } else {
            append('Las horas coinciden exactamente.');
        }

    } catch (err) {
        // Este bloque se activa si hay un error de red o
        // si el AbortController canceló el fetch (timeout).
        append('Timeout (5000 ms) o error al obtener hora.');
    }
};