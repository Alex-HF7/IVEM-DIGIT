"""Configuración del servidor: clave y hosts explícitos obligatorios."""
import os
from .settings_base import *
from .runtime_security import validate_secret, allowed_hosts

SECRET_KEY = validate_secret(os.getenv('IVEM_SECRET_KEY', ''))
ALLOWED_HOSTS = allowed_hosts(os.getenv('IVEM_ALLOWED_HOSTS', ''))
