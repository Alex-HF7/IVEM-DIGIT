"""Errores públicos sin trazas, rutas ni consultas; los detalles quedan en los logs."""
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.urls import get_script_prefix

ERRORS = {
    400: ('Solicitud no válida', 'No pudimos procesar la solicitud. Revisa los datos e inténtalo nuevamente.'),
    403: ('Acceso no permitido', 'No tienes permiso para acceder a esta sección o realizar esta acción.'),
    404: ('No encontramos esta página', 'La página que buscas no existe o ya no está disponible.'),
    405: ('Acción no disponible', 'Esta dirección no admite la acción solicitada. Regresa a la aplicación para continuar.'),
    413: ('Archivo demasiado grande', 'El archivo supera el tamaño permitido. Selecciona uno más pequeño.'),
    429: ('Demasiadas solicitudes', 'Espera un momento antes de volver a intentarlo.'),
    500: ('Ocurrió un problema', 'No pudimos completar la operación. Inténtalo de nuevo más tarde.'),
    503: ('Servicio temporalmente no disponible', 'Estamos teniendo dificultades para atender la solicitud. Inténtalo más tarde.'),
}


def error_response(request, status, csrf=False):
    title, message = ERRORS.get(status, ('No pudimos continuar', 'Regresa a la aplicación e inténtalo nuevamente.'))
    if csrf:
        title, message = 'No se pudo validar el formulario', 'Actualiza la página y vuelve a intentarlo. Si es necesario, inicia sesión nuevamente.'
    accepts = request.headers.get('Accept', '')
    wants_json = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or ('application/json' in accepts and 'text/html' not in accepts)
    if wants_json:
        response = JsonResponse({'success': False, 'status': status, 'message': message}, status=status)
    else:
        # Sin request/context processors: funciona sin consultar usuarios, tablas ni la BD.
        html = render_to_string('errors/error.html', {
            'status': status, 'title': title, 'message': message,
            'home_url': get_script_prefix(),
        })
        response = HttpResponse(html, status=status)
    response['Cache-Control'] = 'no-store'
    response._ivem_friendly_error = True
    return response


def bad_request(request, exception=None):
    return error_response(request, 400)


def permission_denied(request, exception=None):
    return error_response(request, 403)


def page_not_found(request, exception=None):
    return error_response(request, 404)


def server_error(request):
    return error_response(request, 500)


def csrf_failure(request, reason=''):
    return error_response(request, 403, csrf=True)
