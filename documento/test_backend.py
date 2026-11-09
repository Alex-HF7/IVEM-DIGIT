"""Regresiones de permisos y conservación de datos; usan una base temporal."""
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, DatabaseError
from django.test import TestCase, Client
from pypdf import PdfWriter

from gestion_tables.models import ConfiguracionTable
from .utils import saveArchivo


def pdf():
    output = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=100, height=100)
    writer.write(output)
    return SimpleUploadedFile('prueba.pdf', output.getvalue(), content_type='application/pdf')


class BackendProtectionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.admin = User.objects.create_superuser(username='backend_admin', email='', password=None)
        cls.ucg = User.objects.create_user(username='backend_ucg')
        cls.delegacion = User.objects.create_user(username='backend_delegacion')
        cls.ucg.groups.add(Group.objects.get_or_create(name='UCG')[0])
        cls.delegacion.groups.add(Group.objects.get_or_create(name='Delegacion')[0])
        ConfiguracionTable.objects.create(anno=2077)
        with connection.cursor() as cursor:
            for depto in ['ucg', 'delegacion']:
                cursor.execute(f"""INSERT INTO oficios_{depto}_2077
                    (fecha_recibido,fecha_oficio,enviado_por,procedencia,asunto)
                    VALUES ('2077-01-02','2077-01-01','Ana','Local','Pendiente')""")
            cursor.execute("""INSERT INTO oficios_ucg_2077
                (fecha_recibido,fecha_oficio,enviado_por,procedencia,asunto,pendiente)
                VALUES ('2077-01-02','2077-01-01','Ana','Local','Con folio',FALSE)""")
            cursor.execute("""INSERT INTO oficios_ucg_2077
                (fecha_recibido,fecha_oficio,enviado_por,procedencia,asunto,activo)
                VALUES ('2077-01-02','2077-01-01','Ana','Local','Eliminado',FALSE)""")

    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        self.setting = self.settings(MEDIA_ROOT=self.media.name)
        self.setting.enable()
        self.addCleanup(self.setting.disable)
        self.client.force_login(self.admin)

    def row(self, identifier=1):
        with connection.cursor() as cursor:
            cursor.execute('SELECT asunto, archivo, pendiente, folio, activo FROM oficios_ucg_2077 WHERE id=%s', [identifier])
            return cursor.fetchone()

    def upload(self, identifier=1, action='upload', document=None):
        return self.client.post('/manejar-archivo/', {
            'depto':'ucg', 'year':'2077', 'id_oficio':identifier,
            'action':action, 'archivo':document or pdf(),
        })

    def old_file(self):
        name = 'oficios/ucg/2077/1_ucg_2077.pdf'
        path = Path(self.media.name, name)
        path.parent.mkdir(parents=True)
        content = pdf().read()
        path.write_bytes(content)
        with connection.cursor() as cursor:
            cursor.execute('UPDATE oficios_ucg_2077 SET archivo=%s WHERE id=1', [name])
        return name, path, content

    def test_department_groups_restrict_read_write_and_sensitive_actions(self):
        self.client.force_login(self.ucg)
        self.assertEqual(self.client.get('/oficios/ucg/2077/').status_code, 200)
        self.assertEqual(self.client.get('/oficios/delegacion/2077/').status_code, 403)
        self.assertEqual(self.client.get('/oficios/pendientes/').status_code, 403)
        self.assertEqual(self.client.post('/oficios/ucg/2077/1/eliminar/').status_code, 403)
        self.assertEqual(self.client.post('/pendientes/asignar-folio/', {}).status_code, 403)
        self.assertEqual(self.client.post('/manejar-archivo/', {'depto':'delegacion','year':2077,'id_oficio':1,'archivo':pdf()}).status_code,403)
        self.assertTrue(self.row()[4])
        self.client.force_login(self.delegacion)
        self.assertEqual(self.client.get('/oficios/delegacion/2077/').status_code, 200)
        self.assertEqual(self.client.get('/oficios/ucg/2077/').status_code, 403)

    def test_mutations_require_post_and_get_forms_redirect_safely(self):
        for path in ['/oficios/ucg/2077/1/eliminar/', '/pendientes/asignar-folio/', '/manejar-archivo/']:
            self.assertEqual(self.client.get(path).status_code, 405)
        for path in ['/oficios/ucg/2077/crear/', '/oficios/ucg/2077/1/editar/']:
            self.assertRedirects(self.client.get(path), '/oficios/ucg/2077/', fetch_redirect_response=False)
        self.assertTrue(self.row()[4])
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.admin)
        self.assertEqual(csrf_client.post('/oficios/ucg/2077/1/eliminar/').status_code, 403)

    def test_untrusted_table_identifiers_and_paths_are_rejected(self):
        self.assertEqual(self.client.get('/oficios/otro/2077/').status_code, 404)
        self.assertEqual(self.client.post('/pendientes/asignar-folio/', {'tabla_origen':'oficios_ucg_2077; SELECT 1','oficio_id':1}).status_code,404)
        self.assertEqual(self.client.post('/manejar-archivo/', {'depto':'../ucg','year':2077,'id_oficio':1,'archivo':pdf()}).status_code,404)
        self.assertEqual(self.client.post('/manejar-archivo/', {'depto':'ucg','year':'2077; SELECT 1','id_oficio':1,'archivo':pdf()}).status_code,404)
        self.assertEqual(self.client.post('/manejar-archivo/', {'depto':'ucg','year':2077,'id_oficio':'1 OR 1=1','archivo':pdf()}).status_code,404)
        self.assertEqual(self.client.post('/manejar-archivo/', {'depto':'ucg','year':2077,'id_oficio':'9' * 5000,'archivo':pdf()}).status_code,404)
        self.assertEqual(list(Path(self.media.name).rglob('*.pdf')), [])

    def test_finalized_edit_is_blocked_and_missing_pdf_can_still_be_uploaded(self):
        before = self.row(2)
        response = self.client.post('/oficios/ucg/2077/2/editar/', {'asunto':'Cambio prohibido','enviado_por':'Otra persona','procedencia':'Otra'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.row(2), before)
        self.assertEqual(self.upload(2).status_code,200)
        saved = self.row(2)[1]
        self.assertTrue(Path(self.media.name, saved).exists())
        self.assertEqual(self.upload(2, action='edit').status_code,409)
        self.assertEqual(self.upload(2).status_code,409)
        self.assertEqual(self.row(2)[1],saved)

    def test_inactive_and_missing_records_cannot_be_modified(self):
        for identifier in [3,999]:
            self.assertEqual(self.upload(identifier).status_code,404)
            self.assertEqual(self.client.post(f'/oficios/ucg/2077/{identifier}/editar/', {'asunto':'Cambio','enviado_por':'Ana','procedencia':'Local'}).status_code,404)
            self.assertEqual(self.client.get(f'/oficios/imprimir/ucg/2077/{identifier}/').status_code,404)
        self.assertEqual(list(Path(self.media.name).rglob('*.pdf')),[])

    def test_folio_choices_are_validated_and_retry_does_not_advance_sequence(self):
        path='/pendientes/asignar-folio/'
        data={'tabla_origen':'oficios_ucg_2077','oficio_id':1,'asunto_opciones':'inventado','area':'inventada'}
        self.assertEqual(self.client.post(path,data).status_code,302)
        self.assertTrue(self.row()[2])
        data.update(asunto_opciones='conocimiento', area='Sub. Jurídica')
        self.assertEqual(self.client.post(path,data).status_code,302)
        assigned = self.row()[3]
        with connection.cursor() as cursor:
            cursor.execute('SELECT last_value FROM folio_seq_ucg_2077')
            last = cursor.fetchone()[0]
        self.assertEqual(self.client.post(path,data).status_code,302)
        self.assertEqual(self.row()[3],assigned)
        with connection.cursor() as cursor:
            cursor.execute('SELECT last_value FROM folio_seq_ucg_2077')
            self.assertEqual(cursor.fetchone()[0],last)

    def test_fake_pdf_is_rejected_without_touching_old_file(self):
        name,path,content = self.old_file()
        response = self.upload(action='edit', document=SimpleUploadedFile('falso.pdf', b'no es un PDF'))
        self.assertEqual(response.status_code,400)
        self.assertEqual(path.read_bytes(),content)
        self.assertEqual(self.row()[1],name)

    def test_replacement_deletes_old_file_only_after_commit_callback(self):
        name,path,content = self.old_file()
        with self.captureOnCommitCallbacks(execute=True):
            response = self.upload(action='edit')
            self.assertEqual(response.status_code,200)
            self.assertEqual(path.read_bytes(),content)
            saved = self.row()[1]
            self.assertNotEqual(saved,name)
            self.assertTrue(Path(self.media.name,saved).exists())
        self.assertFalse(path.exists())

    def test_storage_failure_preserves_old_reference_and_file(self):
        name,path,content = self.old_file()
        with patch('documento.utils.FileSystemStorage.save',side_effect=OSError('fallo simulado')):
            with self.assertLogs('documento.views',level='ERROR'):
                response = self.upload(action='edit')
        self.assertEqual(response.status_code,500)
        self.assertNotIn('fallo simulado', response.content.decode())
        self.assertEqual(self.row()[1],name)
        self.assertEqual(path.read_bytes(),content)

    def test_database_failure_cleans_new_file_and_preserves_old_file(self):
        name,path,content = self.old_file()
        with patch('documento.utils.connection') as mocked:
            mocked.ops = connection.ops
            cursor = mocked.cursor.return_value.__enter__.return_value
            cursor.fetchone.return_value = (name,True,None)
            cursor.execute.side_effect = [None,DatabaseError('fallo simulado')]
            with self.assertRaises(DatabaseError):
                saveArchivo('ucg',2077,1,pdf(),action='edit')
        self.assertEqual(path.read_bytes(),content)
        self.assertEqual(self.row()[1],name)
        self.assertEqual(list(Path(self.media.name).rglob('*.pdf')),[path])

    def test_statistics_exclude_deleted_records_and_other_departments(self):
        self.client.force_login(self.ucg)
        response = self.client.get('/inicio/',{'mes':'2077-01'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['total_mes'],2)
        self.assertNotContains(response,'Eliminado')

    def test_legacy_pdf_urls_require_login_department_and_active_record(self):
        name,path,content = self.old_file()
        anonymous = Client()
        self.assertEqual(anonymous.get('/media/' + name).status_code,302)
        self.client.force_login(self.delegacion)
        self.assertEqual(self.client.get('/media/' + name).status_code,404)
        self.client.force_login(self.ucg)
        response = self.client.get('/media/' + name)
        self.assertEqual(response.status_code,200)
        self.assertEqual(b''.join(response.streaming_content),content)
        with connection.cursor() as cursor:
            cursor.execute('UPDATE oficios_ucg_2077 SET activo=FALSE WHERE id=1')
        self.assertEqual(self.client.get('/media/' + name).status_code,404)
        self.assertEqual(path.read_bytes(),content)

    def test_audit_all_sensitive_routes_require_login_and_csrf(self):
        anonymous = Client()
        routes = [
            ('get', '/inicio/'), ('get', '/oficios/ucg/2077/'),
            ('get', '/oficios/imprimir/ucg/2077/2/'),
            ('post', '/oficios/ucg/2077/crear/'),
            ('post', '/oficios/ucg/2077/1/editar/'),
            ('post', '/oficios/ucg/2077/1/eliminar/'),
            ('post', '/pendientes/asignar-folio/'), ('post', '/manejar-archivo/'),
        ]
        before = self.row()
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.admin)
        for method, path in routes:
            with self.subTest(method=method, path=path):
                self.assertEqual(getattr(anonymous, method)(path).status_code, 302)
                if method == 'post':
                    self.assertEqual(protected.post(path).status_code, 403)
        self.assertEqual(self.row(), before)

    def test_audit_stored_html_is_escaped_in_listing_and_print(self):
        payload = '<img src=x onerror="alert(1)">'
        with connection.cursor() as cursor:
            cursor.execute('UPDATE oficios_ucg_2077 SET asunto=%s WHERE id=2', [payload])
        for path in ['/oficios/ucg/2077/', '/oficios/imprimir/ucg/2077/2/']:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, payload)
                self.assertContains(response, '&lt;img')

    def test_audit_search_injection_is_literal_and_does_not_modify_records(self):
        before = self.row()
        response = self.client.get('/oficios/ucg/2077/', {'q': "' OR 1=1; DROP TABLE oficios_ucg_2077; --"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.row(), before)
        self.assertNotContains(response, '>Con folio<')

    def test_audit_encrypted_empty_and_wrong_extension_pdfs_preserve_existing_file(self):
        name, path, content = self.old_file()
        encrypted = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt('audit-password')
        writer.write(encrypted)
        empty = BytesIO()
        PdfWriter().write(empty)
        for filename, data in [('encrypted.pdf', encrypted.getvalue()), ('empty.pdf', empty.getvalue()), ('image.html', content)]:
            with self.subTest(filename=filename):
                response = self.upload(action='edit', document=SimpleUploadedFile(filename, data))
                self.assertEqual(response.status_code, 400)
                self.assertEqual(self.row()[1], name)
                self.assertEqual(path.read_bytes(), content)
