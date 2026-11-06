"""Rutas de pruebas: nunca se incluyen en el URLconf de la aplicación."""
from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.http import Http404, HttpResponse, JsonResponse
from django.urls import path
from django.views.decorators.http import require_POST
from . import errors

SECRET = 'PRIVATE_SQL_PASSWORD_PATH_MARKER'


def raise_error(request, code):
    if code == 400:
        raise SuspiciousOperation(SECRET)
    if code == 403:
        raise PermissionDenied(SECRET)
    if code == 404:
        raise Http404(SECRET)
    raise RuntimeError(SECRET)


@require_POST
def post_only(request):
    return HttpResponse('OK')


def unavailable(request):
    response = HttpResponse(SECRET, status=503)
    response['Retry-After'] = '30'
    return response


def json_error(request):
    return JsonResponse({'success': False, 'message': 'Selecciona un PDF válido.'}, status=400)


urlpatterns = [
    path('raise/<int:code>/', raise_error), path('post/', post_only),
    path('unavailable/', unavailable), path('json/', json_error),
]
handler400 = errors.bad_request
handler403 = errors.permission_denied
handler404 = errors.page_not_found
handler500 = errors.server_error
