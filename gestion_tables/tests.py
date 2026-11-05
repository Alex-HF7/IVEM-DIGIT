from io import StringIO
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import connection, DatabaseError
from django.test import TestCase
from django.urls import reverse
from .models import ConfiguracionTable
from .services import create_yearly_tables


class AnnualTableTests(TestCase):
    def exists(self, name):
        with connection.cursor() as cursor:
            cursor.execute('SELECT to_regclass(%s)', [f'public.{name}'])
            return cursor.fetchone()[0] is not None

    def test_creating_configuration_builds_both_tables_sequences_and_triggers(self):
        ConfiguracionTable.objects.create(anno=2060)
        for depto in ['ucg','delegacion']:
            self.assertTrue(self.exists(f'oficios_{depto}_2060'))
            self.assertTrue(self.exists(f'folio_seq_{depto}_2060'))
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname=%s AND NOT tgisinternal", [f'oficios_{depto}_2060',f'trg_set_folio_{depto}_2060'])
                self.assertEqual(cursor.fetchone()[0],1)

    def test_retry_preserves_rows_files_and_sequence_progress(self):
        ConfiguracionTable.objects.create(anno=2061)
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO oficios_ucg_2061 (fecha_recibido,enviado_por,procedencia,asunto,pendiente,archivo) VALUES ('2061-01-01','Ana','Local','Historia',FALSE,'oficios/ucg/2061/antiguo.pdf') RETURNING id,folio,archivo")
            before=cursor.fetchone()
            cursor.execute('SELECT nextval(\'folio_seq_ucg_2061\')')
            progress=cursor.fetchone()[0]
        create_yearly_tables(2061)
        create_yearly_tables(2061)
        with connection.cursor() as cursor:
            cursor.execute('SELECT id,folio,archivo FROM oficios_ucg_2061')
            self.assertEqual(cursor.fetchone(),before)
            cursor.execute('SELECT nextval(\'folio_seq_ucg_2061\')')
            self.assertEqual(cursor.fetchone()[0],progress+1)

    def test_failure_rolls_back_configuration_and_both_departments(self):
        from .services import _create_yearly_tables
        def fail_after_creation(year, conn):
            _create_yearly_tables(year,conn)
            raise DatabaseError('Fallo simulado')
        with patch('gestion_tables.services._create_yearly_tables',side_effect=fail_after_creation):
            with self.assertRaises(DatabaseError):
                ConfiguracionTable.objects.create(anno=2062)
        self.assertFalse(ConfiguracionTable.objects.filter(anno=2062).exists())
        for depto in ['ucg','delegacion']:
            self.assertFalse(self.exists(f'oficios_{depto}_2062'))
            self.assertFalse(self.exists(f'folio_seq_{depto}_2062'))

    def test_missing_sequence_recovers_after_existing_folios_without_rewriting_rows(self):
        ConfiguracionTable.objects.create(anno=2063)
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO oficios_ucg_2063 (fecha_recibido,enviado_por,procedencia,asunto,folio,pendiente) VALUES ('2063-01-01','Ana','Local','Historia',87,FALSE)")
            cursor.execute('DROP SEQUENCE folio_seq_ucg_2063')
        create_yearly_tables(2063)
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO oficios_ucg_2063 (fecha_recibido,enviado_por,procedencia,asunto,pendiente) VALUES ('2063-01-02','Ana','Local','Nuevo',FALSE) RETURNING folio")
            self.assertEqual(cursor.fetchone()[0],88)

    def test_year_is_validated_and_cannot_be_renamed(self):
        for invalid in [0,-1,99,10000]:
            with self.assertRaises(ValidationError):
                ConfiguracionTable.objects.create(anno=invalid)
        config=ConfiguracionTable.objects.create(anno=2064)
        config.anno=2065
        with self.assertRaises(ValidationError):
            config.save()
        config.refresh_from_db()
        self.assertEqual(config.anno,2064)
        self.assertFalse(self.exists('oficios_ucg_2065'))

    def test_disabled_trigger_is_reported_without_overwriting_operator_data(self):
        ConfiguracionTable.objects.create(anno=2070)
        with connection.cursor() as cursor:
            cursor.execute('ALTER TABLE oficios_ucg_2070 DISABLE TRIGGER trg_set_folio_ucg_2070')
        with self.assertRaises(DatabaseError):
            create_yearly_tables(2070)
        with connection.cursor() as cursor:
            cursor.execute("SELECT tgenabled FROM pg_trigger WHERE tgrelid='oficios_ucg_2070'::regclass AND tgname='trg_set_folio_ucg_2070'")
            self.assertEqual(cursor.fetchone()[0],'D')

    def test_existing_sequence_behind_data_is_reported_without_resetting_it(self):
        ConfiguracionTable.objects.create(anno=2071)
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO oficios_ucg_2071 (fecha_recibido,enviado_por,procedencia,asunto,folio,pendiente) VALUES ('2071-01-01','Ana','Local','Historia',87,FALSE)")
        with self.assertRaises(DatabaseError):
            create_yearly_tables(2071)
        with connection.cursor() as cursor:
            cursor.execute('SELECT last_value,is_called FROM folio_seq_ucg_2071')
            self.assertEqual(cursor.fetchone(),(1,False))
            cursor.execute('SELECT folio FROM oficios_ucg_2071')
            self.assertEqual(cursor.fetchone()[0],87)


class AutomaticAdminWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user=get_user_model().objects.create_superuser(username='year_operator',email='',password=None)

    def setUp(self):
        self.client.force_login(self.user)

    def test_operator_creates_and_reads_new_year_without_restart_or_manual_sql(self):
        # Fuerza la carga de rutas antes de crear el nuevo año.
        self.assertEqual(self.client.get('/admin/').status_code,200)
        response=self.client.post('/admin/gestion_tables/configuraciontable/add/',{'anno':2066,'descripcion':'Año nuevo','_save':'Guardar'})
        self.assertEqual(response.status_code,302)
        response=self.client.get('/admin/')
        link=reverse('admin:annual_documents',kwargs={'depto':'ucg','year':2066})
        self.assertContains(response,link)
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO oficios_ucg_2066 (fecha_recibido,enviado_por,procedencia,asunto) VALUES ('2066-01-01','Ana','Local','Documento nuevo')")
        response=self.client.get(link)
        self.assertContains(response,'Documento nuevo')
        self.assertContains(response,'Ana')
        self.assertNotContains(response,'Añadir oficio')
        self.assertContains(self.client.get('/oficios/ucg/2066/'),'Documento nuevo')

    def test_dynamic_models_do_not_generate_migrations_or_allow_admin_writes(self):
        from documento.admin import LazyModelRegistry, dynamic_apps
        from django.apps import apps
        ConfiguracionTable.objects.create(anno=2067)
        LazyModelRegistry.register_all(force=True)
        model=dynamic_apps.all_models['documento']['oficiosucg2067']
        self.assertFalse(model._meta.managed)
        self.assertNotIn('oficiosucg2067',apps.all_models['documento'])
        self.assertIn('fecha_recibido',{field.name for field in model._meta.fields})
        self.assertNotIn('fehca_recibido',{field.name for field in model._meta.fields})
        output=StringIO()
        call_command('makemigrations',check=True,dry_run=True,stdout=output)
        self.assertIn('No changes detected',output.getvalue())

    def test_admin_shows_failure_and_does_not_save_partial_configuration(self):
        with patch('gestion_tables.signals.create_yearly_tables',side_effect=DatabaseError('Fallo simulado')):
            with self.assertLogs('gestion_tables.admin',level='ERROR'):
                response=self.client.post('/admin/gestion_tables/configuraciontable/add/',{'anno':2068,'_save':'Guardar'})
        self.assertEqual(response.status_code,302)
        self.assertFalse(ConfiguracionTable.objects.filter(anno=2068).exists())
        page=self.client.get(response.url)
        self.assertContains(page,'No se guardaron cambios')

    def test_operator_can_complete_missing_objects_from_admin_action(self):
        config=ConfiguracionTable.objects.create(anno=2069)
        with connection.cursor() as cursor:
            cursor.execute("INSERT INTO oficios_ucg_2069 (fecha_recibido,enviado_por,procedencia,asunto,folio,pendiente) VALUES ('2069-01-01','Ana','Local','Conservar',15,FALSE)")
            cursor.execute("SELECT setval('folio_seq_ucg_2069',15)")
            cursor.execute('DROP TABLE oficios_delegacion_2069')
        response=self.client.post('/admin/gestion_tables/configuraciontable/',{
            'action':'verify_selected_years','_selected_action':[str(config.pk)],
        })
        self.assertEqual(response.status_code,302)
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass('public.oficios_delegacion_2069')")
            self.assertIsNotNone(cursor.fetchone()[0])
            cursor.execute('SELECT asunto,folio FROM oficios_ucg_2069')
            self.assertEqual(cursor.fetchone(),('Conservar',15))
