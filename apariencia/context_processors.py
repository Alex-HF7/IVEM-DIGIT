from .services import web_branding


def branding(request):
    if not hasattr(request,'_ivem_branding'):
        request._ivem_branding=web_branding()
    return {'branding':request._ivem_branding}
