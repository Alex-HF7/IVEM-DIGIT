from .errors import error_response


class FriendlyErrorMiddleware:
    """Unifica errores HTTP devueltos por vistas (por ejemplo 405), sin romper JSON."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (response.status_code < 400 or getattr(response, '_ivem_friendly_error', False)
                or 'application/json' in response.get('Content-Type', '')):
            return response
        replacement = error_response(request, response.status_code)
        for name, value in response.items():
            if name.lower() not in {'content-type', 'content-length', 'content-encoding', 'cache-control'}:
                replacement[name] = value
        replacement.cookies.update(response.cookies)
        # La respuesta final cierra los recursos; no adelantar request_finished.
        replacement._resource_closers.extend(response._resource_closers)
        response._resource_closers = []
        return replacement
