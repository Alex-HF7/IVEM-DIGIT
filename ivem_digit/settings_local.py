"""Configuración exclusiva para desarrollo local con Docker Compose."""
from .settings import *

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '[::1]', 'testserver']
# Usa la misma política de registros que la configuración general.
