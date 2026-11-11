"""Registros operativos sin consultas SQL y con retención acotada."""


def build_logging(log_file=None):
    handlers = {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'operational'},
        'discard_sql': {'class': 'logging.NullHandler'},
    }
    active = ['console']
    if log_file:
        handlers['file'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': log_file,
            'maxBytes': 5 * 1024 * 1024,
            'backupCount': 5,
            'encoding': 'utf-8',
            'delay': True,
            'formatter': 'operational',
        }
        active.append('file')
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {'operational': {
            'format': '{asctime} {levelname} {name}: {message}', 'style': '{',
        }},
        'handlers': handlers,
        'root': {'handlers': active, 'level': 'WARNING'},
        'loggers': {
            'django': {'handlers': active, 'level': 'WARNING', 'propagate': False},
            # Bloquea consultas/parámetros incluso si se activa un cursor DEBUG.
            'django.db': {'handlers': ['discard_sql'], 'level': 'WARNING', 'propagate': False},
            'django.db.backends': {'handlers': ['discard_sql'], 'level': 'WARNING', 'propagate': False},
            'django.db.backends.schema': {'handlers': ['discard_sql'], 'level': 'WARNING', 'propagate': False},
        },
    }
