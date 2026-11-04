document.addEventListener('DOMContentLoaded', function () {
    const modal = document.getElementById('editarOficioModal');
    if (!modal) return;

    modal.addEventListener('show.bs.modal', function (event) {
        console.log('modal abierto');
        
        const button = event.relatedTarget;
        if (!button) return;

        const id = button.getAttribute('data-id');
        const asunto = button.getAttribute('data-asunto');
        const referencia = button.getAttribute('data-referencia');
        const enviado_por = button.getAttribute('data-enviado_por');
        const procedencia = button.getAttribute('data-procedencia');

        // Asignar valores a los campos del modal
        document.getElementById('editar_id').value = id;
        document.getElementById('editar_asunto').value = asunto;
        document.getElementById('editar_referencia').value = referencia;
        document.getElementById('editar_enviado_por').value = enviado_por;
        document.getElementById('editar_procedencia').value = procedencia;

        // Definir la acción del formulario
        const form = document.getElementById('formEditarOficio');
        form.action = button.getAttribute('data-url');
    });
});
