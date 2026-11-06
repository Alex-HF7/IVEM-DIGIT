// static/js/submenus.js - Versión mejorada
document.addEventListener('DOMContentLoaded', function() {
    const registro = document.querySelector('.registro-dropdown');
    if (registro) {
        const toggle = registro.querySelector('#navbarDropdown');
        const supportsHover = window.matchMedia('(hover: hover) and (pointer: fine)');
        const dropdown = bootstrap.Dropdown.getOrCreateInstance(toggle, { offset: [0, 0] });

        registro.addEventListener('mouseenter', function() {
            if (supportsHover.matches) dropdown.show();
        });
        registro.addEventListener('mouseleave', function() {
            if (!supportsHover.matches) return;
            dropdown.hide();
            registro.querySelectorAll('.dropdown-submenu .dropdown-menu').forEach(function(menu) {
                menu.classList.remove('show');
            });
        });
    }

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