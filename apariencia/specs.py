# Dimensiones originales: los perfiles nuevos no modifican estos espacios.
SLOTS = {
    'site_logo': ('Logotipo de la navegación', 'ivem.png', 1985, 617),
    'login_logo': ('Logotipo del acceso', 'ivem.png', 1985, 617),
    'favicon': ('Icono de la página', 'Ivem_64px.svg', 64, 64),
    'footer': ('Imagen del pie de página', 'pleca.svg', 300, 16),
    'print_left': ('Imagen izquierda del formato', 'ivem-horizontal.png', 477, 149),
    'print_right': ('Imagen derecha del formato', 'Mich-Mejor.svg', 986.18, 364.74),
}
DEFAULT_COLORS = {'primary':'#682145', 'action':'#0d6efd', 'background':'#f4f6f9', 'text':'#253247', 'accent':'#148575'}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def image_help(slot):
    _, _, width, height = SLOTS[slot]
    return f'Medidas originales: {width} × {height} px (o unidades de viewBox). Recomendado: SVG simple, sin scripts, estilos globales ni recursos externos; preferentemente con texto convertido a curvas. También PNG/JPEG con las medidas indicadas (redondeadas al píxel). Máximo 5 MB.'
