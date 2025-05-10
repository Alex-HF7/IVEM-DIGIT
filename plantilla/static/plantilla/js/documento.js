// Script para manejar acciones dinámicas
document.addEventListener('DOMContentLoaded', function() {
    // Ejemplo: Confirmación antes de eliminar
    document.querySelectorAll('.btn-danger').forEach(btn => {
        btn.addEventListener('click', function(e) {
            if (!confirm('¿Estás seguro de eliminar este oficio?')) {
                e.preventDefault();
            }
        });
    });

    // Mostrar formulario de subida
    document.querySelectorAll('.subir-archivo-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const oficioId = this.getAttribute('data-oficio-id');
            this.style.display = 'none';
            document.querySelector(`.upload-form input[data-oficio-id="${oficioId}"]`)
                .closest('.upload-form').style.display = 'block';
        });
    });
    
    // Cancelar subida
    document.querySelectorAll('.cancel-upload').forEach(btn => {
        btn.addEventListener('click', function() {
            const oficioId = this.closest('.upload-form').querySelector('input').getAttribute('data-oficio-id');
            this.closest('.upload-form').style.display = 'none';
            document.querySelector(`.subir-archivo-btn[data-oficio-id="${oficioId}"]`).style.display = 'inline-block';
        });
    });
    
    // Confirmar subida
    document.querySelectorAll('.confirm-upload').forEach(btn => {
        btn.addEventListener('click', function() {
            const form = this.closest('.upload-form');
            const input = form.querySelector('input[type="file"]');
            const oficioId = input.getAttribute('data-oficio-id');
            
            if (input.files.length === 0) {
                alert('Por favor selecciona un archivo');
                return;
            }
            
            const formData = new FormData();
            formData.append('archivo', input.files[0]);
            
            fetch(`/oficios/${depto}/${year}/${oficioId}/subir-archivo/`, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': csrfToken
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    location.reload(); // Recargar para mostrar el nuevo archivo
                } else {
                    alert('Error al subir el archivo');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Error al subir el archivo');
            });
        });
    });
});