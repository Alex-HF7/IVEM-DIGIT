from django.contrib.auth.forms import AuthenticationForm
from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.exceptions import ValidationError
from django import forms

GENERIC_ERROR = 'Usuario o contraseña incorrectos.'


class PublicAuthenticationForm(AuthenticationForm):
    error_messages = {'invalid_login': GENERIC_ERROR, 'inactive': GENERIC_ERROR}
    username = forms.CharField(max_length=150, label='Usuario', widget=forms.TextInput(attrs={
        'class':'form-control', 'autocomplete':'username', 'autocapitalize':'none',
        'spellcheck':'false', 'autofocus':True,
    }))
    password = forms.CharField(label='Contraseña', strip=False, widget=forms.PasswordInput(attrs={
        'class':'form-control', 'autocomplete':'current-password',
    }))

    def clean(self):
        try:
            return super().clean()
        except ValidationError:
            if getattr(self.request, 'login_service_unavailable', False):
                raise ValidationError('No es posible iniciar sesión en este momento. Inténtalo más tarde.')
            if getattr(self.request, 'login_retry_seconds', 0):
                raise ValidationError('Demasiados intentos. Espera unos minutos antes de volver a intentarlo.')
            raise


class PublicAdminAuthenticationForm(AdminAuthenticationForm):
    error_messages = {'invalid_login': GENERIC_ERROR, 'inactive': GENERIC_ERROR}

    def clean(self):
        try:
            return super().clean()
        except ValidationError:
            if getattr(self.request, 'login_service_unavailable', False):
                raise ValidationError('No es posible iniciar sesión en este momento. Inténtalo más tarde.')
            if getattr(self.request, 'login_retry_seconds', 0):
                raise ValidationError('Demasiados intentos. Espera unos minutos antes de volver a intentarlo.')
            raise
