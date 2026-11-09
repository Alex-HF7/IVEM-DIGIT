"""Configuración sensible, sin valores de respaldo compartidos."""
import ipaddress
import os
from pathlib import Path
import re
import secrets
import tempfile
from django.core.exceptions import ImproperlyConfigured


def validate_secret(value):
    if (len(value) < 50 or len(set(value)) < 5 or
            value.lower().startswith('django-insecure-') or value != value.strip()):
        raise ImproperlyConfigured(
            'Configura IVEM_SECRET_KEY con una clave privada aleatoria de al menos 50 caracteres. '
            'No uses la clave antigua del repositorio.')
    return value


def allowed_hosts(value):
    result = []
    for raw in value.split(','):
        host = raw.strip().lower()
        if not host:
            continue
        try:
            candidate = host[1:-1] if host.startswith('[') and host.endswith(']') else host
            address = ipaddress.ip_address(candidate)
            if '[' in host and address.version != 6:
                raise ValueError('Corchetes solo para IPv6')
            host = f'[{address.compressed}]' if address.version == 6 else str(address)
        except ValueError:
            valid = (len(host) <= 253 and
                     re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?', host) and
                     all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label)
                         for label in host.split('.')) and not re.fullmatch(r'[0-9.]+', host))
            if not valid:
                raise ImproperlyConfigured(
                    'IVEM_ALLOWED_HOSTS solo admite IP o nombres de servidor exactos, '
                    'separados por comas, sin protocolos, puertos ni comodines.')
        if host not in result:
            result.append(host)
    if not result:
        raise ImproperlyConfigured('Configura IVEM_ALLOWED_HOSTS con la IP o dominio del servidor.')
    return result


def development_secret(directory):
    explicit = os.getenv('IVEM_SECRET_KEY', '')
    if explicit:
        return validate_secret(explicit)
    directory = Path(directory)
    target = directory / 'secret-key'
    try:
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if not target.exists():
            # Publica solo un archivo completo, incluso con arranques simultáneos.
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=directory,
                                                 delete=False) as stream:
                    temporary = Path(stream.name)
                    stream.write(secrets.token_urlsafe(64))
                try:
                    os.link(temporary, target)
                except FileExistsError:
                    pass
            finally:
                if temporary:
                    temporary.unlink(missing_ok=True)
        return validate_secret(target.read_text(encoding='utf-8'))
    except OSError as error:
        raise ImproperlyConfigured(
            'No se pudo acceder a la clave local. Comprueba permisos de .local '
            'o configura IVEM_SECRET_KEY. No elimines la clave para resolverlo.') from error
