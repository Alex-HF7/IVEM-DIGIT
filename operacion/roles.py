"""Nombres públicos de perfiles; el acceso se comprueba por permiso."""
DOCUMENT_GROUP = 'Administración de oficios'
USER_GROUP = 'Gestión de usuarios'
FOLDER_GROUP = 'Gestión de carpetas'
TECHNICAL_GROUP = 'Acceso técnico Django'
OPERATIONAL_GROUPS = ('UCG', 'Delegacion', DOCUMENT_GROUP, USER_GROUP, FOLDER_GROUP)
TECH_PERMISSION = 'gestion_tables.access_technical_admin'


def can_enter_admin(user):
    return (user.is_authenticated and user.is_active and
            (user.is_superuser or (user.is_staff and user.has_perm(TECH_PERMISSION))))
