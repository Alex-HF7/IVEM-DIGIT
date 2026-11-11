from django.apps import AppConfig


class LoginConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'login'

    def ready(self):
        from django.contrib import admin
        from .forms import PublicAdminAuthenticationForm
        admin.site.login_form = PublicAdminAuthenticationForm
