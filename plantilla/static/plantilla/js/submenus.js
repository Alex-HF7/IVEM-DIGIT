// static/js/submenus.js - Versión mejorada
document.addEventListener('DOMContentLoaded', function() {
    // Manejar submenús desplegables con Bootstrap
    function setupBootstrapSubmenus() {
        const dropdownSubmenus = document.querySelectorAll('.dropdown-submenu');
        
        dropdownSubmenus.forEach(function(submenu) {
            const toggle = submenu.querySelector('.dropdown-toggle');
            const menu = submenu.querySelector('.dropdown-menu');
            
            // Mostrar/ocultar al hacer clic
            toggle.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                // Cerrar otros submenús primero
                document.querySelectorAll('.dropdown-submenu .dropdown-menu').forEach(function(m) {
                    if (m !== menu) {
                        m.classList.remove('show');
                    }
                });
                
                // Alternar el actual
                menu.classList.toggle('show');
            });
            
            // Cerrar al hacer clic fuera
            document.addEventListener('click', function(e) {
                if (!submenu.contains(e.target)) {
                    menu.classList.remove('show');
                }
            });
        });
    }
    
    // Inicializar
    setupBootstrapSubmenus();
});