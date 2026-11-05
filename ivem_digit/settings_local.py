"""Configuración exclusiva para desarrollo local con Docker Compose."""
from .settings import *

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]', 'testserver']
# Evita modificar el archivo SQL versionado; Docker captura la salida.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'loggers': {'django.db': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False}},
}
