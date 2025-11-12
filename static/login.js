// static/login.js
document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('loginForm');
    const emailInput = document.querySelector('input[name="email"]');
    const passwordInput = document.querySelector('input[name="password"]');

    loginForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const email = emailInput.value.trim();
        const password = passwordInput.value;

        // Validar formato de correo UDG
        if (!email.endsWith('.udg.mx')) {
            showAlert('Solo se permiten correos institucionales de la UDG', 'error');
            emailInput.focus();
            return;
        }
        
        // Validar que el correo tenga formato válido
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email)) {
            showAlert('Por favor ingresa un correo electrónico válido', 'error');
            emailInput.focus();
            return;
        }

        // Validar que la contraseña no esté vacía
        if (!password) {
            showAlert('Por favor ingresa tu contraseña', 'error');
            passwordInput.focus();
            return;
        }
        
        // Mostrar loading
        const submitBtn = loginForm.querySelector('.submit-btn');
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = 'Iniciando sesión... ⌛';
        submitBtn.disabled = true;

        // Enviar formulario
        fetch(loginForm.action, {
            method: 'POST',
            body: new FormData(loginForm)
        })
        .then(response => {
            if (response.redirected) {
                // Redirección exitosa (login correcto)
                window.location.href = response.url;
            } else {
                // Error en el login
                return response.text().then(html => {
                    const parser = new DOMParser();
                    const doc = parser.parseFromString(html, 'text/html');
                    const errorElement = doc.querySelector('.error');
                    const errorMessage = errorElement ? errorElement.textContent : 'Error desconocido';
                    throw new Error(errorMessage);
                });
            }
        })
        .catch(error => {
            showAlert(error.message, 'error');
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        });
    });
    
    // Mostrar alertas
    function showAlert(message, type, autoRemoveTime = 5000) {
        const existingAlerts = document.querySelectorAll('.alert');
        existingAlerts.forEach(alert => alert.remove());
        
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert ${type}`;
        alertDiv.innerHTML = `<strong>${type === 'success' ? '✅' : '❌'}</strong> ${message}`;
        
        const h2 = document.querySelector('h2');
        h2.parentNode.insertBefore(alertDiv, h2.nextSibling);
        
        if (autoRemoveTime > 0) {
            setTimeout(() => {
                if (alertDiv.parentNode) {
                    alertDiv.remove();
                }
            }, autoRemoveTime);
        }
    }

    // Focus en el primer campo al cargar
    emailInput.focus();
});