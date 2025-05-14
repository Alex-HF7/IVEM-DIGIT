document.addEventListener('DOMContentLoaded', function() {
  const botones = document.querySelectorAll('.btn-cargar-pdf');
  
  botones.forEach(function(boton) {
    boton.addEventListener('click', function() {
      const depto = boton.getAttribute('data-depto');
      const year = boton.getAttribute('data-year');
      const oficioId = boton.getAttribute('data-oficio-id');
      
      const form = document.getElementById('formCargarArchivo');
      // Actualiza la URL exacta como está en urls.py
      form.action = `/oficios/${depto}/${year}/${oficioId}/cargar/`;
      
      // Debug: Verifica en consola
      console.log('URL actualizada:', form.action);
      
      // Actualiza campo oculto si es necesario
      if(document.getElementById('modalOficioId')) {
        document.getElementById('modalOficioId').value = oficioId;
      }
    });
  });
});