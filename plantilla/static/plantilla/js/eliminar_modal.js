document.addEventListener('DOMContentLoaded', function () {
  const modal = document.getElementById('modalEliminarGlobal');

  if (modal) {
    modal.addEventListener('show.bs.modal', function (event) {
      const button = event.relatedTarget;

      const id = button.getAttribute('data-id');

      const url = button.getAttribute('data-url');

      // Actualiza el formulario
      const form = modal.querySelector('#formEliminarGlobal');
      form.action = url;

      // Muestra el folio en el texto del modal
      const folioSpan = modal.querySelector('#folioEliminar');
      folioSpan.textContent = `#${id}`;
    });
  }
});
