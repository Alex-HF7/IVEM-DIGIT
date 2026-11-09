from django.db import migrations

PERMISSIONS = [
    ('view_all_documents', 'Consultar oficios de todos los departamentos'),
    ('view_pending_documents', 'Consultar el listado de pendientes'),
    ('assign_folio', 'Asignar folios a oficios'),
    ('delete_document', 'Eliminar oficios de forma lógica'),
    ('access_technical_admin', 'Acceder a la administración técnica Django'),
]


def create_roles(apps, schema_editor):
    alias = schema_editor.connection.alias
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Permission = apps.get_model('auth', 'Permission')
    Group = apps.get_model('auth', 'Group')
    User = apps.get_model('auth', 'User')
    if (User.objects.using(alias).filter(is_staff=True).exists() and
            not User.objects.using(alias).filter(is_staff=True, is_superuser=True, is_active=True).exists()):
        raise RuntimeError('Debe existir un superusuario activo antes de restringir Django Admin. Crea o habilita uno mediante el responsable técnico.')
    config_type, _ = ContentType.objects.using(alias).get_or_create(app_label='gestion_tables', model='configuraciontable')
    user_type, _ = ContentType.objects.using(alias).get_or_create(app_label='auth', model='user')
    custom = {}
    for code, name in PERMISSIONS:
        custom[code], _ = Permission.objects.using(alias).get_or_create(content_type=config_type, codename=code, defaults={'name': name})
    roles = {
        'Administración de oficios': [custom[code] for code, _ in PERMISSIONS if code != 'access_technical_admin'],
        'Acceso técnico Django': [custom['access_technical_admin']],
    }
    for group_name, content_type, codes in [
        ('Gestión de usuarios', user_type, ['add_user', 'view_user']),
        ('Gestión de carpetas', config_type, ['add_configuraciontable', 'view_configuraciontable']),
    ]:
        roles[group_name] = []
        for code in codes:
            permission, _ = Permission.objects.using(alias).get_or_create(content_type=content_type, codename=code, defaults={'name': code})
            roles[group_name].append(permission)
    for name in ['UCG', 'Delegacion']:
        Group.objects.using(alias).get_or_create(name=name)
    for name, permissions in roles.items():
        group, _ = Group.objects.using(alias).get_or_create(name=name)
        expected = {permission.pk for permission in permissions}
        existing = set(group.permissions.values_list('pk', flat=True))
        if existing - expected:
            raise RuntimeError('Un perfil de gestión existente contiene permisos adicionales. Revísalo antes de aplicar esta migración: ' + name)
        if group.user_set.exists() and expected - existing:
            raise RuntimeError('Un perfil existente tiene miembros y permisos diferentes. Revísalo antes de conceder facultades nuevas: ' + name)
        group.permissions.add(*permissions)
    # Conserva las facultades documentales previas; no concede altas de usuarios,
    # carpetas, acceso técnico ni nuevos permisos de apariencia a staff existentes.
    operators = Group.objects.using(alias).get(name='Administración de oficios')
    for user in User.objects.using(alias).filter(is_staff=True, is_superuser=False).iterator():
        user.groups.add(operators)


class Migration(migrations.Migration):
    dependencies = [('gestion_tables', '0001_initial'), ('auth', '0012_alter_user_first_name_max_length'), ('contenttypes', '0002_remove_content_type_name')]
    operations = [
        migrations.AlterModelOptions(name='configuraciontable', options={
            'verbose_name': 'Configuración de Tabla', 'verbose_name_plural': 'Configuración de Tablas', 'permissions': PERMISSIONS,
        }),
        migrations.RunPython(create_roles, migrations.RunPython.noop),
    ]
