/**
 * Redimensiona una imagen desde un objeto File.
 * Mantiene la proporción y la convierte a un string Base64.
 *
 * @param {File} file - El archivo de imagen a redimensionar.
 * @param {number} maxWidth - El ancho máximo deseado.
 * @param {number} maxHeight - El alto máximo deseado.
 * @param {number} quality - La calidad del JPEG (0.0 a 1.0).
 * @returns {Promise<string>} Una promesa que se resuelve con el string Base64.
 */
function resizeImage(file, maxWidth = 800, maxHeight = 800, quality = 0.7) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        
        // Se activa cuando el archivo se carga en memoria
        reader.onload = (event) => {
            const img = new Image();
            
            // Se activa cuando la imagen se decodifica
            img.onload = () => {
                let width = img.width;
                let height = img.height;

                // Calcular nuevas dimensiones manteniendo la proporción
                if (width > height) {
                    if (width > maxWidth) {
                        height = Math.round(height * (maxWidth / width));
                        width = maxWidth;
                    }
                } else {
                    if (height > maxHeight) {
                        width = Math.round(width * (maxHeight / height));
                        height = maxHeight;
                    }
                }

                // Crear un canvas para dibujar la imagen redimensionada
                const canvas = document.createElement('canvas');
                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext('2d');
                
                // Dibujar la imagen en el canvas
                ctx.drawImage(img, 0, 0, width, height);

                // Obtener el string Base64 del canvas
                // 'image/jpeg' es usualmente más ligero que 'image/png'
                const dataUrl = canvas.toDataURL('image/jpeg', quality);
                
                resolve(dataUrl);
            };
            
            // Se activa si la imagen está corrupta o no es válida
            img.onerror = (error) => {
                reject(error);
            };

            // Cargar la imagen desde el resultado del FileReader
            img.src = event.target.result;
        };
        
        // Se activa si hay un error leyendo el archivo
        reader.onerror = (error) => {
            reject(error);
        };
        
        // Empezar a leer el archivo
        reader.readAsDataURL(file);
    });
}