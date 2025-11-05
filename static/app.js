// flask_microservice/static/app.js
let es = null;
const messages = document.getElementById('messages');
const input = document.getElementById('input');
const sendBtn = document.getElementById('send');
const connectBtn = document.getElementById('btnConnect');
const usernameInput = document.getElementById('username');
const getTimeBtn = document.getElementById('getTime');

function append(msg) {
    messages.textContent += msg + '\n';
    messages.scrollTop = messages.scrollHeight;
}

connectBtn.onclick = () => {
    if (es) {
        append('Ya estás conectado al stream.');
        return;
    }
    append('Conectando al stream SSE...');
    es = new EventSource('/chat/stream');
    es.onmessage = function (e) {
        append(e.data);
    };
    es.onerror = function (e) {
        append('Error SSE, reintentando...');
        // el navegador intentará reconectar automáticamente
    };
};

sendBtn.onclick = async () => {
    const name = usernameInput.value.trim() || 'Anon';
    const text = input.value.trim();
    if (!text) return;
    const payload = { message: `[${new Date().toLocaleTimeString()}] ${name}: ${text}` };
    try {
        const r = await fetch('/chat/send', {
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

input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendBtn.click();
});

// GET /time and compare with local time (timeout 5000ms)
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
        const serverTimeStr = data.time; // HH:MM:SS
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
