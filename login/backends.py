import logging
import redis
from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import PermissionDenied
from . import throttle

logger = logging.getLogger(__name__)


class LimitedModelBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        # Comandos internos sin una petición HTTP no representan intentos remotos.
        if request is None or not username or not password:
            return super().authenticate(request, username, password, **kwargs)
        try:
            keys, retry = throttle.reserve(request, username)
            if retry:
                request.login_retry_seconds = retry
                raise PermissionDenied
            user = super().authenticate(request, username, password, **kwargs)
            if user is not None:
                throttle.success(keys)
            return user
        except redis.RedisError:
            request.login_service_unavailable = True
            logger.error('El servicio de protección de acceso no está disponible')
            # No permitir que un fallo de caché elimine la protección.
            raise PermissionDenied
