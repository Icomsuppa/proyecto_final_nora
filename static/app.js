// --- Variables Globales ---

// La conexión al stream de Server-Sent Events (SSE).
let es = null;

// --- Selección de Elementos del DOM ---

const messages = document.getElementById('messages');
const sendBtn = document.getElementById('send');
const connectBtn = document.getElementById('btnConnect');
const usernameInput = document.getElementById('username');
const getTimeBtn = document.getElementById('getTime');
const imageInput = document.getElementById('imageInput');
const sendImageBtn = document.getElementById('sendImageBtn');


// --- Funciones Auxiliares ---

/**
 * Agrega un nodo (texto o HTML) al área de mensajes
 * y se asegura de que la vista se desplace hacia abajo.
 * @param {string|Node} content - El mensaje de texto o un elemento (ej. <img>).
 */
function append(content) {
    if (typeof content === 'string') {
        // Si es texto, crea un párrafo para él
        const p = document.createElement('p');
        p.textContent = content;
        messages.appendChild(p);
    } else {
        // Si es un nodo (como una imagen), lo agrega directamente
        messages.appendChild(content);
    }
    // Mueve el scroll del div hasta el final
    messages.scrollTop = messages.scrollHeight;
}

// --- Lógica de Eventos (Botones) ---

/**
 * Manejador del clic para el botón 'Conectar'.
 */
connectBtn.onclick = () => {
    if (es) {
        append('Ya estás conectado al stream.');
        return;
    }

    append('Conectando al stream SSE...');
    es = new EventSource('/chat/stream');
    append('Ya estas Conectado');

    /**
     * Se activa cada vez que el servidor envía un mensaje.
     * Ahora debe parsear JSON y decidir qué hacer.
     */
    es.onmessage = function (e) {
        let data;
        try {
            // e.data ahora es un string JSON enviado por el servidor
            data = JSON.parse(e.data);
        } catch (err) {
            // Si falla, es un mensaje de texto simple
            append(e.data);
            return;
        }

        const name = data.user || 'Anon';

        // Decidir qué tipo de mensaje es
        if (data.type === 'chat') {
            // --- Mensaje de chat normal ---
            const text = data.text || '';
            append(`[${name}]: ${text}`);

        } else if (data.type === 'image') {
            const filename = data.filename;
            const sender_ip = data.sender_ip; // La IP que el listener de Python agregó

            if (!filename || !sender_ip) {
                append(`[${name}] intentó enviar una imagen, pero hubo un error.`);
                return;
            }

            const imageUrl = `http://${sender_ip}:5000/chat/temp_images/${filename}`;

            append(`[${name}] envió una imagen:`);
            
            // Crea el elemento de imagen
            const img = document.createElement('img');
            img.src = imageUrl;
            img.alt = `Imagen de ${name}`;
            img.className = 'chat-image'; // Para CSS
            img.style.maxWidth = '400px';
            img.style.maxHeight = '400px';
            img.style.borderRadius = '8px';
            img.style.marginTop = '4px';
            img.style.marginBottom = '4px';
            
            img.onload = () => messages.scrollTop = messages.scrollHeight;
            
            append(img); // Agrega la imagen al chat
        }
    };

    /**
     * Se activa si hay un error en la conexión SSE.
     */
    es.onerror = function (e) {
        append('Error SSE, reintentando...');
    };
};

/**
 * Envía un payload JSON
 */
sendBtn.onclick = async () => {
    const name = usernameInput.value.trim() || 'Anon';
    const text = input.value.trim();

    if (!text) return;

    const payload = { 
        type: "chat", // Especificamos el tipo
        user: name,
        message: text // 'message' en lugar de 'text' para coincidir con el python
    };

    try {
        const r = await fetch('/chat/send', { // /send ahora espera este JSON
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!r.ok) {
            append('Error al enviar mensaje al servidor.');
        } else {
            input.value = '';
        }
    } catch (e) {
        append('Error de red al enviar mensaje.');
    }
};

/**
 * Agrega un listener al campo de texto para que la tecla 'Enter'
 * también envíe el mensaje.
 */
input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        sendBtn.click();
    }
});

/**
 * Manejador del clic para el botón 'Obtener Hora'.
 */
getTimeBtn.onclick = async () => {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), 5000);

    try {
        const resp = await fetch('/time/', { signal: controller.signal });
        clearTimeout(id);

        if (!resp.ok) {
            append('Error al pedir hora al servidor');
            return;
        }

        const data = await resp.json();
        const serverTimeStr = data.time;
        const serverParts = serverTimeStr.split(':').map(x => parseInt(x, 10));
        const nowLocal = new Date();
        const serverNow = new Date(nowLocal.getFullYear(), nowLocal.getMonth(), nowLocal.getDate(),
            serverParts[0], serverParts[1], serverParts[2]);

        const diffMs = nowLocal - serverNow;
        const diffSec = Math.round(diffMs / 1000);

        append(`Hora servidor: ${data.date} ${data.time}`);
        append(`Hora local: ${nowLocal.toLocaleString()}`);
        
        if (diffSec > 0) append(`La hora local está ${diffSec} segundos ADELANTADA.`);
        else if (diffSec < 0) append(`La hora local está ${-diffSec} segundos ATRASADA.`);
        else append('Las horas coinciden exactamente.');

    } catch (err) {
        append('Timeout (5000 ms) o error al obtener hora.');
    }
};



/**
 * Conecta el botón visible "Subir Foto" al input[type=file] invisible.
 */
sendImageBtn.onclick = () => {
    imageInput.click(); // Abre el explorador de archivos
};

/**
 * Se activa cuando el usuario selecciona un archivo de imagen.
 */
imageInput.onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const name = usernameInput.value.trim() || 'Anon';
    append('Redimensionando imagen...');

    try {
        // Usa la función del script 'image_resizer.js'
        const imageBase64 = await resizeImage(file, 800, 800, 0.7);

        append('Subiendo imagen...');
        
        const payload = {
            user: name,
            image_b64: imageBase64
        };

        // Llama a la nueva ruta del backend
        const r = await fetch('/chat/upload_image', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!r.ok) {
            append('Error al subir la imagen.');
        } else {
            append('Imagen enviada.');
        }

    } catch (err) {
        append('Error al procesar la imagen.');
        console.error(err);
    } finally {
        // Resetea el input para poder subir la misma foto otra vez
        imageInput.value = null;
    }
};