"""Configuración exclusiva para desarrollo local con Docker Compose."""
from .settings_base import *
from .runtime_security import development_secret

SECRET_KEY = development_secret(BASE_DIR / '.local')
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]', 'testserver']
