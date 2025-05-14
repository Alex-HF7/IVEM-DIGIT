class ArchivoModal {
    constructor() {
        this.modal = new bootstrap.Modal(document.getElementById('cargarArchivoModal'));
        this.form = document.getElementById('formCargarArchivo');
        this.alertContainer = document.getElementById('alertContainer');
        this.initEvents();
    }
    
    initEvents() {
        // Botones para abrir modal
        document.querySelectorAll('.btn-cargar-archivo').forEach(btn => {
            btn.addEventListener('click', (e) => this.setupModal(e.target));
        });
        
        // Envío del formulario
        this.form.addEventListener('submit', (e) => this.handleSubmit(e));
        
        // Reset al cerrar modal
        this.modal._element.addEventListener('hidden.bs.modal', () => this.resetForm());
    }
    
    setupModal(button) {
        const depto = button.getAttribute('data-depto');
        const year = button.getAttribute('data-year');
        const idOficio = button.getAttribute('data-id');
        
        document.getElementById('modalDepto').value = depto;
        document.getElementById('modalYear').value = year;
        document.getElementById('modalIdOficio').value = idOficio;
        document.getElementById('cargarArchivoModalLabel').textContent = 
            `Cargar Archivo - Oficio ${idOficio} (${depto} ${year})`;
        
        this.resetForm();
        this.modal.show();
    }
    
    async handleSubmit(e) {
        e.preventDefault();
        this.alertContainer.innerHTML = '';
        
        try {
            const formData = new FormData(this.form);
            console.log("Enviando a:", this.form.action);
            const response = await fetch(this.form.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': formData.get('csrfmiddlewaretoken')
                }
            });
            
            const data = await response.json();
            
            if (!response.ok) throw new Error(data.message || 'Error en la solicitud');
            
            if (data.success) {
                this.showAlert('success', data.message);
                setTimeout(() => window.location.reload(), 1500);
            } else {
                this.showAlert('danger', data.message);
            }
        } catch (error) {
            console.error('Error:', error);
            this.showAlert('danger', error.message || 'Error al procesar la solicitud');
        }
    }
    
    showAlert(type, message) {
        this.alertContainer.innerHTML = `
            <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
    }
    
    resetForm() {
        this.form.reset();
        this.alertContainer.innerHTML = '';
    }
}

// Inicialización cuando el DOM está listo
document.addEventListener('DOMContentLoaded', () => {
    new ArchivoModal();
});