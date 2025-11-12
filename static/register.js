// static/register.js - VERSIÓN MEJORADA
console.log("🟢 register.js cargado");

document.addEventListener('DOMContentLoaded', function() {
    console.log("🟢 DOM cargado");
    
    const registerForm = document.getElementById('registerForm');
    const emailInput = document.querySelector('input[name="email"]');
    const profileImageInput = document.getElementById('profileImage');
    
    console.log("🟢 Formulario encontrado:", registerForm);
    console.log("🟢 Input de imagen encontrado:", profileImageInput);

    // Debug de cambio de archivo
    profileImageInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        console.log("🟢 Archivo seleccionado:", file);
        if (file) {
            console.log("📁 Detalles del archivo:");
            console.log("   - nombre:", file.name);
            console.log("   - tipo:", file.type);
            console.log("   - tamaño:", file.size, "bytes");
            console.log("   - último modificado:", file.lastModified);
            
            // Mostrar en UI también
            showAlert(`Imagen seleccionada: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`, 'success', 3000);
        }
    });

    // Validación y envío del formulario - VERSIÓN MEJORADA
    registerForm.addEventListener('submit', function(e) {
        e.preventDefault(); // ✅ Prevenir envío normal
        
        console.log("🟢 Formulario enviado (preventDefault)");
        
        const email = emailInput.value.trim();
        const formData = new FormData(registerForm);
        
        console.log("🟢 FormData creado, entries:", Array.from(formData.entries()));

        // Validar formato de correo UDG
        if (!email.endsWith('.udg.mx')) {
            showAlert('Solo se permiten correos institucionales de la UDG (terminan en .udg.mx)', 'error');
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
        
        // Validar tamaño de archivo (max 5MB)
        if (profileImageInput.files.length > 0) {
            const file = profileImageInput.files[0];
            const maxSize = 5 * 1024 * 1024; // 5MB en bytes
            
            console.log("📏 Validando archivo:", file.name, "- Tamaño:", file.size);
            
            if (file.size > maxSize) {
                showAlert('La imagen debe ser menor a 5MB', 'error');
                profileImageInput.value = '';
                return;
            }
            
            // Validar tipo de archivo
            const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png'];
            if (!allowedTypes.includes(file.type)) {
                showAlert('Solo se permiten imágenes JPEG, JPG o PNG', 'error');
                profileImageInput.value = '';
                return;
            }
        }
        
        // Mostrar loading
        const submitBtn = registerForm.querySelector('.submit-btn');
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = 'Registrando... ⌛';
        submitBtn.disabled = true;

        console.log("🟢 Enviando petición fetch...");
        
        // Enviar formulario via Fetch API
        fetch(registerForm.action, {
            method: 'POST',
            body: formData
        })
        .then(response => {
            console.log("🟢 Respuesta recibida, status:", response.status);
            return response.json().then(data => ({ status: response.status, data }));
        })
        .then(({ status, data }) => {
            console.log("🟢 Datos de respuesta:", data);
            
            if (status === 201 && data.success) {
                // ✅ REGISTRO EXITOSO
                showAlert(data.message, 'success');
                console.log("✅ Registro exitoso, redirigiendo...");
                
                // Redirigir después de 3 segundos
                setTimeout(() => {
                    window.location.href = data.redirect_url;
                }, 3000);
                
            } else if (data.error) {
                // ❌ ERROR
                showAlert(data.error, 'error');
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            } else {
                // ❌ ERROR INESPERADO
                showAlert('Error inesperado en el registro', 'error');
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            }
        })
        .catch(error => {
            console.error('❌ Error de conexión:', error);
            showAlert('Error de conexión con el servidor', 'error');
            submitBtn.innerHTML = originalText;
            submitBtn.disabled = false;
        });
    });
    
    // Mostrar alertas - VERSIÓN MEJORADA
    function showAlert(message, type, autoRemoveTime = 5000) {
        // Remover alertas existentes
        const existingAlerts = document.querySelectorAll('.alert');
        existingAlerts.forEach(alert => alert.remove());
        
        // Crear nueva alerta
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert ${type}`;
        alertDiv.innerHTML = `
            <strong>${type === 'success' ? '✅' : '❌'}</strong> 
            ${message}
        `;
        
        // Insertar después del h2
        const h2 = document.querySelector('h2');
        h2.parentNode.insertBefore(alertDiv, h2.nextSibling);
        
        // Scroll suave a la alerta
        alertDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
        
        // Auto-remover después del tiempo especificado
        if (autoRemoveTime > 0) {
            setTimeout(() => {
                if (alertDiv.parentNode) {
                    alertDiv.style.opacity = '0';
                    alertDiv.style.transition = 'opacity 0.5s ease';
                    setTimeout(() => {
                        if (alertDiv.parentNode) {
                            alertDiv.remove();
                        }
                    }, 500);
                }
            }, autoRemoveTime);
        }
    }
    
    // Función para preview de imagen (opcional mejorado)
    function showImagePreview(file) {
        const reader = new FileReader();
        reader.onload = function(e) {
            // Remover preview anterior
            const oldPreview = document.getElementById('imagePreview');
            const oldRemoveBtn = document.getElementById('removePreviewBtn');
            if (oldPreview) oldPreview.remove();
            if (oldRemoveBtn) oldRemoveBtn.remove();
            
            // Crear nuevo preview
            const previewContainer = document.createElement('div');
            previewContainer.style.marginTop = '10px';
            previewContainer.style.textAlign = 'center';
            
            const preview = document.createElement('img');
            preview.id = 'imagePreview';
            preview.src = e.target.result;
            preview.style.maxWidth = '150px';
            preview.style.maxHeight = '150px';
            preview.style.borderRadius = '8px';
            preview.style.border = '2px solid #667eea';
            preview.style.boxShadow = '0 2px 10px rgba(0,0,0,0.1)';
            
            const removeBtn = document.createElement('button');
            removeBtn.id = 'removePreviewBtn';
            removeBtn.textContent = '✕ Quitar imagen';
            removeBtn.type = 'button';
            removeBtn.style.marginTop = '5px';
            removeBtn.style.padding = '5px 10px';
            removeBtn.style.background = '#ff6b6b';
            removeBtn.style.color = 'white';
            removeBtn.style.border = 'none';
            removeBtn.style.borderRadius = '4px';
            removeBtn.style.cursor = 'pointer';
            removeBtn.style.fontSize = '12px';
            
            removeBtn.addEventListener('click', function() {
                profileImageInput.value = '';
                previewContainer.remove();
                showAlert('Imagen removida', 'success', 2000);
            });
            
            previewContainer.appendChild(preview);
            previewContainer.appendChild(document.createElement('br'));
            previewContainer.appendChild(removeBtn);
            
            // Insertar después del input de archivo
            profileImageInput.parentNode.appendChild(previewContainer);
        };
        reader.readAsDataURL(file);
    }
    
    // Activar preview automáticamente si hay archivo seleccionado
    profileImageInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        if (file) {
            console.log('🖼️ Imagen seleccionada:', file.name, '- Tamaño:', (file.size / 1024 / 1024).toFixed(2) + 'MB');
            showImagePreview(file);
        }
    });

    // Debug adicional: mostrar todos los campos del formulario
    console.log("🔍 Campos del formulario encontrados:");
    const formFields = registerForm.querySelectorAll('input, select');
    formFields.forEach(field => {
        console.log(`   - ${field.name}: ${field.type || 'select'}`);
    });
});