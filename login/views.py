from django.contrib.auth.views import LoginView
from ivem_digit.errors import error_response
from .forms import PublicAuthenticationForm


class SecureLoginView(LoginView):
    template_name = 'login/login.html'
    authentication_form = PublicAuthenticationForm
    redirect_authenticated_user = True

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if response.status_code in {200, 302, 429}:
            response['Content-Security-Policy'] = (
                "default-src 'self'; script-src 'self'; "
                "style-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
                "font-src 'self' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://michoacan.gob.mx; "
                "img-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
            )
        response['Referrer-Policy'] = 'same-origin'
        return response

    def form_invalid(self, form):
        for field in ('username', 'password'):
            form.fields[field].widget.attrs.update({'aria-invalid':'true','aria-describedby':'login-feedback'})
        if getattr(self.request, 'login_service_unavailable', False):
            return error_response(self.request,503)
        response = super().form_invalid(form)
        retry = getattr(self.request, 'login_retry_seconds', 0)
        if retry:
            response.status_code = 429
            response['Retry-After'] = str(retry)
            response._ivem_friendly_error = True
        response['Cache-Control'] = 'no-store'
        return response
