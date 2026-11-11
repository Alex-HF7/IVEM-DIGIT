"""Etiquetas de interfaz; no modifica nombres de grupos ni sus permisos."""
from .roles import DOCUMENT_GROUP, USER_GROUP, FOLDER_GROUP, TECHNICAL_GROUP

ROLE_PRESENTATION = {
    'UCG': ('UCG', 'Registrar y consultar oficios de la Unidad de Control de Gestión.', 'department'),
    'Delegacion': ('Delegación Administrativa', 'Registrar y consultar oficios de Delegación.', 'department'),
    DOCUMENT_GROUP: ('Administrar oficios', 'Todos los departamentos: pendientes, asignación de folios y eliminación lógica.', 'advanced'),
    USER_GROUP: ('Usuarios', 'Crear y consultar usuarios. No permite delegar acceso técnico.', 'advanced'),
    FOLDER_GROUP: ('Carpetas anuales', 'Crear y consultar las carpetas de cada año.', 'advanced'),
    TECHNICAL_GROUP: ('Acceso técnico', 'Entrar a Django Admin. Solo para personal técnico; no concede otros permisos.', 'advanced'),
}


def role_label(name):
    return ROLE_PRESENTATION.get(name, (name, '', 'advanced'))[0]
