class ArchivoModal {
    constructor() {
        this.modal = new bootstrap.Modal(document.getElementById('archivoModal')); // Cambiado el ID
        this.form = document.getElementById('formArchivo'); // Cambiado el ID
        this.currentFileContainer = document.getElementById('currentFileContainer');
        this.initEvents();
    }
    
    initEvents() {
        // Botones para abrir modal (cargar y editar)
        document.querySelectorAll('.btn-cargar-archivo, .btn-editar-archivo').forEach(btn => {
           btn.addEventListener('click', (e) => this.setupModal(e.target));
        });
        
        // Envío del formulario
        this.form.addEventListener('submit', (e) => this.handleSubmit(e));
        
        // Reset al cerrar modal
        this.modal._element.addEventListener('hidden.bs.modal', () => this.resetForm());
    }
    
    setupModal(element) {
        this.resetForm();
        const button = element.closest('button');
        const isEdit = button.classList.contains('btn-editar-archivo');

        const depto = button.getAttribute('data-depto');
        const year = button.getAttribute('data-year');
        const idOficio = button.getAttribute('data-id');
        const fileName = button.getAttribute('data-file-name');
        const fileUrl = button.getAttribute('data-file-url');
        
        console.log('Valores reales:', { depto, year, idOficio, isEdit });

        // Configurar campos ocultos
        document.getElementById('modalDepto').value = depto;
        document.getElementById('modalYear').value = year;
        document.getElementById('modalIdOficio').value = idOficio;
        document.getElementById('modalAction').value = isEdit ? 'edit' : 'upload';

        // Configurar título y texto del botón
        const modalTitle = document.getElementById('archivoModalLabel');
        const submitBtn = this.form.querySelector('button[type="submit"]');
        
        if (isEdit) {
            modalTitle.textContent = `Editar Archivo - Oficio ${idOficio} (${depto} ${year})`;
            submitBtn.textContent = 'Actualizar';
            
            // Mostrar información del archivo actual
            this.currentFileContainer.classList.remove('d-none');
            document.getElementById('currentFileName').textContent = fileName || 'Archivo actual';
            
            const fileLink = document.getElementById('currentFileLink');
            if (fileUrl) {
                fileLink.href = fileUrl;
                fileLink.classList.remove('d-none');
            } else {
                fileLink.classList.add('d-none');
            }
        } else {
            modalTitle.textContent = `Cargar Archivo - Oficio ${idOficio} (${depto} ${year})`;
            submitBtn.textContent = 'Cargar';
            this.currentFileContainer.classList.add('d-none');
        }
        
        this.modal.show();
    }
    
    async handleSubmit(e) {
    e.preventDefault();
    
    const submitBtn = this.form.querySelector('button[type="submit"]');
    const originalBtnText = submitBtn.textContent;
    
    try {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Procesando...';
        
        const fileInput = document.getElementById('archivoInput');
        const file = fileInput.files[0];
        if (file && file.size > Number(fileInput.dataset.maxBytes)) {
            throw new Error(`El PDF no puede superar ${fileInput.dataset.maxMb} MB.`);
        }
        const formData = new FormData(this.form);
        const actionUrl = this.form.getAttribute('action'); // Obtiene la URL correcta
        
        console.log("Enviando a:", actionUrl); // Verifica que sea la URL correcta
        
        const response = await fetch(actionUrl, {  // Usa actionUrl aquí
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': formData.get('csrfmiddlewaretoken'),
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        
        // Verifica si la respuesta es JSON válido
        const textResponse = await response.text();
        let data;
        
        try {
            data = JSON.parse(textResponse);
        } catch (jsonError) {
            console.error('Error parsing JSON:', jsonError);
            throw new Error('La respuesta del servidor no es válida');
        }
        
        if (!response.ok) {
            throw new Error(data.message || `Error ${response.status}: ${response.statusText}`);
        }
        
        if (data.success) {
            // El mensaje de Django se mostrará como toast después de recargar.
            this.modal.hide();
            window.location.reload();
        } else {
            throw new Error(data.message || 'Error al procesar el archivo');
        }
    } catch (error) {
        console.error('Error:', error);
        window.showAppToast('danger', error.message || 'Error al procesar la solicitud');
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = originalBtnText;
    }
}
    
    resetForm() {
        this.form.reset();
    }
}

// Inicialización cuando el DOM está listo
document.addEventListener('DOMContentLoaded', () => {
    new ArchivoModal();
});