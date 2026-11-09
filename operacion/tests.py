from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch
from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.admin.models import LogEntry
from django.db import connection, DatabaseError
from django.test import TestCase, Client
from gestion_tables.models import ConfiguracionTable
from documento.access import allowed_departments
from .roles import DOCUMENT_GROUP, USER_GROUP, FOLDER_GROUP, TECHNICAL_GROUP


class OperationalManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.root = User.objects.create_superuser(username='management_root', email='', password=None)
        cls.staff = User.objects.create_user(username='plain_staff', is_staff=True)
        cls.manager = User.objects.create_user(username='account_manager')
        cls.manager.groups.add(Group.objects.get(name=USER_GROUP))
        cls.folder_manager = User.objects.create_user(username='folder_manager')
        cls.folder_manager.groups.add(Group.objects.get(name=FOLDER_GROUP))
        cls.document_manager = User.objects.create_user(username='document_manager')
        cls.document_manager.groups.add(Group.objects.get(name=DOCUMENT_GROUP))

    def user_data(self, **extra):
        return {'username': 'new_operator', 'first_name': 'Ana', 'last_name': 'Prueba',
                'password1': 'LocalAudit#74529XY', 'password2': 'LocalAudit#74529XY',
                'groups': [Group.objects.get(name='UCG').pk], **extra}

    def test_authentication_permissions_and_csrf_guard_both_screens(self):
        for url in ('/gestion/usuarios/', '/gestion/carpetas/'):
            self.assertEqual(self.client.get(url).status_code, 302)
            self.client.force_login(self.staff)
            self.assertEqual(self.client.get(url).status_code, 403)
            self.assertEqual(self.client.post(url, {}).status_code, 403)
            self.client.logout()
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.root)
        self.assertEqual(csrf.post('/gestion/usuarios/', self.user_data()).status_code, 403)
        self.assertEqual(csrf.post('/gestion/carpetas/', {'anno': 2053}).status_code, 403)

    def test_staff_alone_grants_neither_documents_nor_technical_admin(self):
        self.assertEqual(allowed_departments(self.staff), set())
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get('/oficios/pendientes/').status_code, 403)
        self.assertEqual(self.client.post('/oficios/ucg/2026/1/eliminar/').status_code, 403)
        self.assertEqual(self.client.get('/admin/').status_code, 302)
        self.assertEqual(self.client.get('/admin/auth/user/').status_code, 302)
        self.assertNotContains(self.client.get('/inicio/'), 'Administración técnica</a>')

    def test_operational_document_manager_needs_no_staff_flag(self):
        self.client.force_login(self.document_manager)
        self.assertEqual(allowed_departments(self.document_manager), {'ucg', 'delegacion'})
        self.assertEqual(self.client.get('/oficios/pendientes/').status_code, 200)
        self.assertEqual(self.client.get('/admin/').status_code, 302)
        self.assertEqual(self.client.get('/gestion/usuarios/').status_code, 403)

    def test_user_manager_creates_hashed_operator_without_privilege_escalation(self):
        self.client.force_login(self.manager)
        self.assertContains(self.client.get('/gestion/usuarios/'), 'Agregar nuevo usuario')
        self.assertEqual(self.client.post('/gestion/usuarios/', self.user_data()).status_code, 302)
        user = get_user_model().objects.get(username='new_operator')
        self.assertTrue(user.check_password('LocalAudit#74529XY'))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(allowed_departments(user), {'ucg'})
        self.assertTrue(LogEntry.objects.filter(user=self.manager, object_id=str(user.pk)).exists())
        for field in ('is_staff', 'is_superuser', 'user_permissions'):
            with self.subTest(field=field):
                response = self.client.post('/gestion/usuarios/', self.user_data(username='forged', **{field: '1'}))
                self.assertContains(response, 'No se pueden modificar privilegios')
                self.assertFalse(get_user_model().objects.filter(username='forged').exists())

    def test_manager_cannot_delegate_technical_or_operational_management_roles(self):
        self.client.force_login(self.manager)
        for name in (TECHNICAL_GROUP, DOCUMENT_GROUP, USER_GROUP, FOLDER_GROUP):
            response = self.client.post('/gestion/usuarios/', self.user_data(groups=[Group.objects.get(name=name).pk]))
            self.assertEqual(response.status_code, 200)
            self.assertFalse(get_user_model().objects.filter(username='new_operator').exists())
        # Un grupo departamental modificado con permisos elevados tampoco es delegable.
        Group.objects.get(name='UCG').permissions.add(Permission.objects.get(codename='change_user'))
        self.client.post('/gestion/usuarios/', self.user_data())
        self.assertFalse(get_user_model().objects.filter(username='new_operator').exists())

    def test_superuser_can_create_limited_technical_account_but_not_superuser(self):
        self.client.force_login(self.root)
        self.assertEqual(self.client.post('/gestion/usuarios/', self.user_data(groups=[Group.objects.get(name=TECHNICAL_GROUP).pk])).status_code, 302)
        user = get_user_model().objects.get(username='new_operator')
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.client.force_login(user)
        self.assertEqual(self.client.get('/admin/').status_code, 200)
        self.assertEqual(self.client.get('/admin/auth/user/').status_code, 403)
        self.assertEqual(allowed_departments(user), set())

    def test_password_and_duplicate_user_validation_do_not_create_accounts(self):
        self.client.force_login(self.manager)
        self.client.post('/gestion/usuarios/', self.user_data(password1='123', password2='123'))
        self.assertFalse(get_user_model().objects.filter(username='new_operator').exists())
        self.assertEqual(self.client.post('/gestion/usuarios/', self.user_data()).status_code, 302)
        self.assertEqual(self.client.post('/gestion/usuarios/', self.user_data()).status_code, 200)
        self.assertEqual(get_user_model().objects.filter(username='new_operator').count(), 1)

    def test_folder_creation_builds_both_departments_and_rejects_duplicates(self):
        self.client.force_login(self.folder_manager)
        self.assertEqual(self.client.post('/gestion/carpetas/', {'anno': 2053, 'descripcion': 'Nuevo año'}).status_code, 302)
        with connection.cursor() as cursor:
            for dept in ('ucg', 'delegacion'):
                cursor.execute('SELECT to_regclass(%s)', [f'oficios_{dept}_2053'])
                self.assertIsNotNone(cursor.fetchone()[0])
        self.assertEqual(self.client.post('/gestion/carpetas/', {'anno': 2053}).status_code, 200)
        self.assertEqual(ConfiguracionTable.objects.filter(anno=2053).count(), 1)
        self.assertEqual(self.client.post('/gestion/carpetas/', {'anno': '2053; DROP TABLE auth_user'}).status_code, 200)
        self.assertEqual(self.client.get('/admin/').status_code, 302)

    def test_folder_failure_rolls_back_and_does_not_show_internal_error(self):
        self.client.force_login(self.folder_manager)
        with patch('gestion_tables.signals.create_yearly_tables', side_effect=DatabaseError('PRIVATE_DATABASE_DETAIL')):
            with self.assertLogs('operacion.views', level='ERROR'):
                response = self.client.post('/gestion/carpetas/', {'anno': 2054})
        self.assertContains(response, 'No se guardaron cambios')
        self.assertNotContains(response, 'PRIVATE_DATABASE_DETAIL')
        self.assertFalse(ConfiguracionTable.objects.filter(anno=2054).exists())

    def test_view_only_permission_does_not_allow_creations(self):
        self.staff.user_permissions.add(Permission.objects.get(codename='view_user'))
        self.client.force_login(self.staff)
        self.assertContains(self.client.get('/gestion/usuarios/'), 'Cuentas registradas')
        self.assertNotContains(self.client.get('/gestion/usuarios/'), 'Agregar nuevo usuario')
        self.assertEqual(self.client.post('/gestion/usuarios/', self.user_data()).status_code, 403)

    def test_role_migration_preserves_previous_staff_documents_only(self):
        before = self.staff.password
        migration = import_module('gestion_tables.migrations.0002_operational_roles')
        migration.create_roles(apps, SimpleNamespace(connection=connection))
        migration.create_roles(apps, SimpleNamespace(connection=connection))
        user = get_user_model().objects.get(pk=self.staff.pk)
        self.assertEqual(user.password, before)
        self.assertEqual(allowed_departments(user), {'ucg', 'delegacion'})
        self.assertFalse(user.has_perm('auth.add_user'))
        self.assertFalse(user.has_perm('gestion_tables.access_technical_admin'))
        self.assertFalse(user.has_perm('gestion_tables.add_configuraciontable'))

    def test_document_actions_remain_limited_to_authorized_department(self):
        user = get_user_model().objects.create_user(username='limited_documents')
        user.groups.add(Group.objects.get(name='UCG'))
        user.user_permissions.add(Permission.objects.get(codename='delete_document'))
        ConfiguracionTable.objects.create(anno=2055)
        with connection.cursor() as cursor:
            for dept in ('ucg', 'delegacion'):
                cursor.execute(f"INSERT INTO oficios_{dept}_2055 (fecha_recibido,fecha_oficio,enviado_por,procedencia,asunto) VALUES ('2055-01-02','2055-01-01','Prueba','Local','Permisos')")
        self.client.force_login(user)
        self.assertEqual(self.client.post('/oficios/ucg/2055/1/eliminar/').status_code, 302)
        self.assertEqual(self.client.post('/oficios/delegacion/2055/1/eliminar/').status_code, 403)
        self.assertEqual(self.client.post('/pendientes/asignar-folio/', {}).status_code, 403)
        with connection.cursor() as cursor:
            cursor.execute('SELECT activo FROM oficios_delegacion_2055 WHERE id=1')
            self.assertTrue(cursor.fetchone()[0])

    def test_menu_only_exposes_authorized_management_screens(self):
        self.client.force_login(self.manager)
        response = self.client.get('/inicio/')
        self.assertContains(response, 'href="/gestion/usuarios/"')
        self.assertNotContains(response, 'href="/gestion/carpetas/"')
        self.assertNotContains(response, 'href="/admin/"')
        self.client.force_login(self.folder_manager)
        response = self.client.get('/inicio/')
        self.assertContains(response, 'href="/gestion/carpetas/"')
        self.assertNotContains(response, 'href="/gestion/usuarios/"')

    def test_migration_refuses_name_collision_with_more_powerful_existing_role(self):
        group = Group.objects.get(name=DOCUMENT_GROUP)
        group.permissions.add(Permission.objects.get(codename='change_user'))
        migration = import_module('gestion_tables.migrations.0002_operational_roles')
        with self.assertRaisesMessage(RuntimeError, 'permisos adicionales'):
            migration.create_roles(apps, SimpleNamespace(connection=connection))
        self.assertFalse(self.staff.groups.filter(pk=group.pk).exists())

    def test_migration_requires_recovery_superuser_when_staff_already_exist(self):
        get_user_model().objects.filter(pk=self.root.pk).update(is_active=False)
        migration = import_module('gestion_tables.migrations.0002_operational_roles')
        with self.assertRaisesMessage(RuntimeError, 'superusuario activo'):
            migration.create_roles(apps, SimpleNamespace(connection=connection))
        self.assertFalse(self.staff.groups.filter(name=DOCUMENT_GROUP).exists())

    def test_migration_does_not_grant_new_permissions_to_members_of_name_collision(self):
        group = Group.objects.get(name=FOLDER_GROUP)
        permission = Permission.objects.get(codename='add_configuraciontable')
        group.permissions.remove(permission)
        migration = import_module('gestion_tables.migrations.0002_operational_roles')
        with self.assertRaisesMessage(RuntimeError, 'miembros y permisos diferentes'):
            migration.create_roles(apps, SimpleNamespace(connection=connection))
        self.assertFalse(group.permissions.filter(pk=permission.pk).exists())

    def test_profile_cards_preserve_advanced_selection_after_validation_error(self):
        self.client.force_login(self.root)
        response = self.client.get('/gestion/usuarios/')
        self.assertContains(response, 'Delegación Administrativa')
        self.assertContains(response, 'Acceso por departamento')
        self.assertContains(response, 'Permisos adicionales')
        response = self.client.post('/gestion/usuarios/', self.user_data(
            password1='123', password2='123', groups=[Group.objects.get(name=TECHNICAL_GROUP).pk]))
        self.assertContains(response, '<details class="advanced-profiles mt-3" open>')
        self.assertNotContains(response, 'value="123"')
        self.assertFalse(get_user_model().objects.filter(username='new_operator').exists())
        self.client.force_login(self.manager)
        self.assertNotContains(self.client.get('/gestion/usuarios/'), 'Permisos adicionales')
