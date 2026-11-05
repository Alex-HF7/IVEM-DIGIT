from django.template.loader import render_to_string
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import resolve, reverse, set_script_prefix

from . import views


class DocumentURLTests(SimpleTestCase):
    def test_edit_and_delete_routes(self):
        kwargs = {'depto': 'ucg', 'year': 2026, 'id': 7}
        for name, suffix in [('editar_oficio', 'editar'), ('eliminar_oficio', 'eliminar')]:
            url = reverse(name, kwargs=kwargs)
            self.assertEqual(url, f'/oficios/ucg/2026/7/{suffix}/')
            self.assertEqual(resolve(url).kwargs, kwargs)

    def test_legacy_edit_route_keeps_same_view(self):
        match = resolve('/oficio/ucg/2026/7/editar')
        self.assertEqual(match.func.__wrapped__, views.editar_oficio)
        self.assertEqual(match.kwargs, {'depto': 'ucg', 'year': 2026, 'id': 7})

    @override_settings(MEDIA_URL='/documentos/')
    def test_templates_use_generated_urls_and_media_setting(self):
        # Keep template checks independent of database context processors.
        context = {
            'depto': 'ucg', 'year': 2026, 'es_staff': True,
            'user': {'is_authenticated': True, 'is_staff': True},
            'oficios': [{'id': 7, 'folio': None, 'archivo': 'archivos/prueba.pdf'}],
        }
        html = render_to_string('documento/lista_oficios.html', context)
        self.assertIn('data-url="/oficios/ucg/2026/7/editar/"', html)
        self.assertIn('data-url="/oficios/ucg/2026/7/eliminar/"', html)
        self.assertIn('href="/documentos/archivos/prueba.pdf"', html)
        self.assertIn('href="' + reverse('admin:auth_user_changelist') + '"', html)
        pending = render_to_string('documento/lista_pendientes.html', context)
        self.assertIn('href="/documentos/archivos/prueba.pdf"', pending)

    def test_generated_form_urls_respect_deployment_prefix(self):
        set_script_prefix('/ivem/')
        try:
            html = render_to_string('documento/lista_oficios.html', {
                'depto': 'ucg', 'year': 2026, 'es_staff': True,
                'oficios': [{'id': 7, 'folio': None}],
            })
            self.assertIn('data-url="/ivem/oficios/ucg/2026/7/editar/"', html)
            self.assertIn('data-url="/ivem/oficios/ucg/2026/7/eliminar/"', html)
        finally:
            set_script_prefix('/')


class DynamicAdminTests(SimpleTestCase):
    def test_registers_models_before_building_admin_urls(self):
        from unittest.mock import patch
        from django.contrib.admin import AdminSite, ModelAdmin
        from django.contrib.auth.models import Group, User
        from django.urls import URLResolver
        from .admin import LazyModelRegistry

        site = AdminSite(name='dynamic_test')
        site.register(User, ModelAdmin)

        def register_dynamic_model():
            site.register(Group, ModelAdmin)
            return True

        with patch.object(LazyModelRegistry, '_registered', False):
            with patch('documento.admin.registrar_modelo_dinamico', side_effect=register_dynamic_model) as register:
                urls = site.get_urls()
                patterns = [str(url.pattern) for url in urls if isinstance(url, URLResolver)]
                self.assertIn('auth/group/', patterns)
                site.get_urls()
                register.assert_called_once_with()

    def test_failed_registration_can_be_retried(self):
        from unittest.mock import patch
        from .admin import LazyModelRegistry

        with patch.object(LazyModelRegistry, '_registered', False):
            with patch('documento.admin.registrar_modelo_dinamico', side_effect=[False, True]) as register:
                LazyModelRegistry.register_all()
                self.assertFalse(LazyModelRegistry._registered)
                LazyModelRegistry.register_all()
                self.assertTrue(LazyModelRegistry._registered)
                self.assertEqual(register.call_count, 2)


class DashboardTests(SimpleTestCase):
    def test_spanish_months_chronology_and_integer_axes(self):
        from datetime import date
        from .dashboard import dashboard_statistics
        result = dashboard_statistics([
            {'fecha_recibido': date(2026, 1, 10), 'pendiente': True, 'departamento': 'ucg'},
            {'fecha_recibido': date(2025, 12, 20), 'pendiente': False, 'departamento': 'delegacion'},
        ], date(2026, 1, 15))
        self.assertEqual(result['current_month'], 'enero de 2026')
        self.assertEqual(result['total_mes'], 1)
        self.assertEqual(result['pendientes_mes'], 1)
        figure = result['fig_nuevos']
        self.assertEqual(figure.layout.xaxis.type, 'category')
        self.assertEqual(list(figure.layout.xaxis.categoryarray), ['diciembre 2025', 'enero 2026'])
        self.assertEqual(figure.layout.yaxis.dtick, 1)
        self.assertEqual({trace.name for trace in figure.data}, {'UCG', 'Delegación'})

    def test_current_month_excludes_same_month_in_previous_year(self):
        from datetime import date
        from .dashboard import dashboard_statistics
        result = dashboard_statistics([
            {'fecha_recibido': date(2025, 11, 6), 'pendiente': True, 'departamento': 'ucg'},
            {'fecha_recibido': date(2026, 11, 5), 'pendiente': False, 'departamento': 'delegacion'},
        ], date(2026, 11, 5))
        self.assertEqual(result['total_mes'], 1)
        self.assertEqual(result['pendientes_mes'], 0)

    def test_zero_pending_and_empty_dashboard_render(self):
        from datetime import date
        from .dashboard import dashboard_statistics
        result = dashboard_statistics([
            {'fecha_recibido': date(2026, 11, 5), 'pendiente': False, 'departamento': 'ucg'},
        ], date(2026, 11, 5))
        self.assertIsNone(result['fig_pendientes'])
        html = render_to_string('documento/grafica.html', result)
        self.assertIn('Sin pendientes', html)
        empty = dashboard_statistics([], date(2026, 11, 5))
        self.assertTrue(empty['no_data'])
        self.assertIn('Aún no hay oficios', render_to_string('documento/grafica.html', empty))


class NewDocumentFormTests(SimpleTestCase):
    def test_received_date_defaults_to_local_today_and_remains_editable(self):
        from datetime import datetime, timezone as datetime_timezone
        from html.parser import HTMLParser
        from unittest.mock import patch
        from django.test import RequestFactory
        from django.utils import timezone

        class DateInputs(HTMLParser):
            def __init__(self):
                super().__init__()
                self.inputs = {}

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if tag == 'input' and attrs.get('type') == 'date':
                    self.inputs[attrs['name']] = attrs

        # Después de medianoche UTC todavía es el día anterior en México.
        with timezone.override('America/Mexico_City'):
            with patch('django.utils.timezone.now', return_value=datetime(2026, 11, 6, 2, tzinfo=datetime_timezone.utc)):
                for depto in ['ucg', 'delegacion']:
                    with self.subTest(depto=depto):
                        request = RequestFactory().get(f'/oficios/{depto}/2026/')
                        with patch('documento.views.buscar_oficios', return_value=([], '')), patch('documento.views.render') as render:
                            views.lista_oficios(request, depto, 2026)
                        context = render.call_args.args[2]
                        html = render_to_string('documento/lista_oficios.html', context)
                        parser = DateInputs()
                        parser.feed(html)
                        received = parser.inputs['fecha_recibido']
                        self.assertEqual(received['value'], '2026-11-05')
                        self.assertNotIn('readonly', received)
                        self.assertNotIn('disabled', received)
                        self.assertNotIn('value', parser.inputs['fecha_oficio'])


class FileNotificationTests(SimpleTestCase):
    def test_upload_and_edit_queue_success_for_toast_after_reload(self):
        from unittest.mock import patch
        from django.contrib.messages import get_messages
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import RequestFactory
        import json

        for action in ['upload', 'edit']:
            with self.subTest(action=action):
                request = RequestFactory().post('/manejar-archivo/', {
                    'depto': 'ucg', 'year': '2026', 'id_oficio': '2', 'action': action,
                    'archivo': SimpleUploadedFile('prueba.pdf', b'%PDF-1.4 test'),
                })
                request.session = {}
                request._messages = FallbackStorage(request)
                with patch('documento.views.saveArchivo', return_value='archivos/prueba.pdf'), patch('documento.views.connection'):
                    response = views.archivo(request)
                self.assertTrue(json.loads(response.content)['success'])
                messages = list(get_messages(request))
                self.assertEqual(len(messages), 1)
                self.assertEqual(messages[0].tags, 'success')
                self.assertIn('actualizado' if action == 'edit' else 'cargado', str(messages[0]))

    def test_folio_form_has_unique_labels_and_optional_multiline_note(self):
        from html.parser import HTMLParser

        class Elements(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids = []
                self.labels = []
                self.notes = []

            def handle_starttag(self, tag, attrs):
                attrs = dict(attrs)
                if 'id' in attrs:
                    self.ids.append(attrs['id'])
                if tag == 'label':
                    self.labels.append(attrs.get('for'))
                if tag == 'textarea' and attrs.get('name') == 'nota':
                    self.notes.append(attrs)

        html = render_to_string('documento/lista_pendientes.html', {'oficios': [
            {'id': 2, 'tabla_origen': 'oficios_ucg_2026', 'asunto': 'Prueba'},
            {'id': 2, 'tabla_origen': 'oficios_delegacion_2026', 'asunto': 'Otra prueba'},
        ]})
        parser = Elements()
        parser.feed(html)
        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        for label in parser.labels:
            self.assertIn(label, parser.ids)
        self.assertEqual(len(parser.notes), 2)
        self.assertTrue(all('required' not in note for note in parser.notes))
        self.assertIn('id="appToastContainer"', html)


class AssignedDepartmentChartTests(SimpleTestCase):
    def test_groups_by_assigned_area_instead_of_origin_department(self):
        from datetime import date
        from .dashboard import dashboard_statistics
        records = [
            {'departamento': 'ucg', 'area': 'Sub. Jurídica'},
            {'departamento': 'delegacion', 'area': 'Sub. Jurídica'},
            {'departamento': 'delegacion', 'area': 'UCG'},
            {'departamento': 'ucg', 'area': None},
            {'departamento': 'ucg', 'area': '  '},
        ]
        for record in records:
            record.update(fecha_recibido=date(2026, 11, 5), pendiente=False)
        result = dashboard_statistics(records, date(2026, 11, 5))
        chart = result['fig_areas']
        counts = {area: int(count) for trace in chart.data for area, count in zip(trace.y, trace.x)}
        self.assertEqual(counts, {'Subdirección Jurídica': 2, 'UCG': 1, 'Sin área asignada': 2})
        self.assertEqual(sum(counts.values()), result['total_oficios'])
        self.assertEqual(chart.layout.xaxis.tickformat, 'd')


class PDFLimitTests(SimpleTestCase):
    @override_settings(PDF_MAX_MB=1)
    def test_oversized_pdf_is_rejected_before_replacing_existing_file(self):
        from unittest.mock import patch
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import RequestFactory
        for action in ['upload', 'edit']:
            request = RequestFactory().post('/manejar-archivo/', {
                'depto': 'ucg', 'year': '2026', 'id_oficio': '1', 'action': action,
                'archivo': SimpleUploadedFile('prueba.pdf', b'x' * (1024 * 1024 + 1)),
            })
            with patch('documento.views.saveArchivo') as save:
                response = views.archivo(request)
            self.assertEqual(response.status_code, 400)
            self.assertIn('1 MB', response.content.decode())
            save.assert_not_called()


class DatabaseSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.db import connection
        from gestion_tables.models import ConfiguracionTable
        ConfiguracionTable.objects.create(anno=2090)
        cls.tables = ['oficios_ucg_2090', 'oficios_delegacion_2090']
        with connection.cursor() as cursor:
            for index, table in enumerate(cls.tables):
                cursor.execute(f'INSERT INTO {table} (fecha_recibido, enviado_por, procedencia, asunto, area, pendiente) VALUES (%s,%s,%s,%s,%s,%s)',
                               ['2090-01-05', 'María', 'DIRECCIÓN', 'Informe jurídico', 'Sub. Jurídica', index == 0])
            cursor.executemany('INSERT INTO oficios_ucg_2090 (fecha_recibido,enviado_por,procedencia,asunto) VALUES (%s,%s,%s,%s)',
                               [('2090-01-05', 'Ana', 'Local', f'Seguimiento {i}') for i in range(45)])
            for subject in ['100%_final', '100AXfinal']:
                cursor.execute('INSERT INTO oficios_ucg_2090 (fecha_recibido,enviado_por,procedencia,asunto) VALUES (%s,%s,%s,%s)',
                               ['2090-01-05', 'Ana', 'Local', subject])
            cursor.execute("INSERT INTO oficios_ucg_2090 (fecha_recibido,enviado_por,procedencia,asunto,activo) VALUES ('2090-01-05','Ana','Local','Informe jurídico',FALSE)")

    def test_search_combines_words_ignoring_case_and_accents_across_tables(self):
        from django.test import RequestFactory
        from .utils import buscar_oficios
        request = RequestFactory().get('/', {'q': 'INFORME juridico direccion'})
        page, query = buscar_oficios(request, self.tables)
        self.assertEqual(page.paginator.count, 2)
        self.assertEqual({row['tabla_origen'] for row in page}, set(self.tables))
        pending, _ = buscar_oficios(request, self.tables, pendientes=True)
        self.assertEqual(pending.paginator.count, 1)
        self.assertTrue(pending[0]['pendiente'])

    def test_literal_wildcards_and_invalid_identifiers(self):
        from django.test import RequestFactory
        from .utils import buscar_oficios
        request = RequestFactory().get('/', {'q': '100%_final'})
        page, _ = buscar_oficios(request, self.tables)
        self.assertEqual(page.paginator.count, 1)
        self.assertEqual(page[0]['asunto'], '100%_final')
        with self.assertRaises(ValueError):
            buscar_oficios(request, ['oficios_ucg_2090; DROP TABLE auth_user'])

    def test_database_pagination_uses_two_queries_and_keeps_search_in_links(self):
        from django.test import RequestFactory
        from .utils import buscar_oficios
        request = RequestFactory().get('/', {'q': 'seguimiento', 'page': 2})
        with self.assertNumQueries(2):
            page, query = buscar_oficios(request, self.tables)
        self.assertEqual(page.paginator.count, 45)
        self.assertEqual(len(page), 20)
        self.assertEqual(page.start_index(), 21)
        html = render_to_string('documento/includes/pagination.html', {'page': page, 'search_query': query})
        self.assertIn('aria-current="page"', html)
        self.assertIn('?q=seguimiento&amp;page=3', html)
        following, _ = buscar_oficios(RequestFactory().get('/', {'q':'seguimiento', 'page':3}), self.tables)
        self.assertEqual(len(following), 5)
        self.assertFalse({row['id'] for row in page} & {row['id'] for row in following})


class DashboardMonthNavigationTests(SimpleTestCase):
    def test_month_navigation_crosses_year_boundaries_and_rejects_invalid_values(self):
        from datetime import date
        from .dashboard import dashboard_period
        today = date(2026, 11, 5)
        january = dashboard_period('2026-01', today)
        self.assertEqual(january['previous_month'], '2025-12')
        self.assertEqual(january['next_month'], '2026-02')
        self.assertEqual(january['period_start'], date(2025, 2, 1))
        self.assertEqual(january['period_end'], date(2026, 2, 1))
        self.assertEqual(dashboard_period('2026-12', today)['next_month'], '2027-01')
        for invalid in ['2026-13', '2026-00', 'texto', '2026-1', '0000-01']:
            result = dashboard_period(invalid, today)
            self.assertTrue(result['invalid_month'])
            self.assertEqual(result['selected_month'], '2026-11')

    def test_only_selected_month_is_used_for_pending_and_assigned_charts(self):
        from datetime import date
        from .dashboard import dashboard_statistics
        result = dashboard_statistics([
            {'fecha_recibido': date(2026, 10, 2), 'pendiente': True, 'departamento':'ucg', 'area':'UCG'},
            {'fecha_recibido': date(2026, 11, 2), 'pendiente': False, 'departamento':'delegacion', 'area':'Sub. Jurídica'},
        ], date(2026, 11, 1))
        self.assertEqual(result['total_mes'], 1)
        self.assertEqual(result['pendientes_mes'], 0)
        self.assertIsNone(result['fig_pendientes'])
        self.assertEqual(list(result['fig_areas'].data[0].y), ['Subdirección Jurídica'])
        empty = dashboard_statistics([
            {'fecha_recibido': date(2026, 10, 2), 'pendiente': True, 'departamento':'ucg', 'area':'UCG'},
        ], date(2026, 11, 1))
        self.assertEqual(empty['total_mes'], 0)
        self.assertIsNone(empty['fig_areas'])
        self.assertIsNotNone(empty['fig_nuevos'])


class RequiredDatesAndHistoricalDashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model
        from django.db import connection
        from gestion_tables.models import ConfiguracionTable
        cls.user = get_user_model().objects.create_superuser(username='date_test', email='', password=None)
        ConfiguracionTable.objects.create(anno=2088)
        with connection.cursor() as cursor:
            cursor.execute("""INSERT INTO oficios_ucg_2088 (fecha_recibido, fecha_oficio, enviado_por, procedencia, asunto, pendiente, area)
                              VALUES ('2088-12-05','2088-12-01','Ana','Local','Diciembre',TRUE,'UCG') RETURNING id""")
            cls.record_id = cursor.fetchone()[0]
            cursor.execute("""INSERT INTO oficios_delegacion_2088 (fecha_recibido, fecha_oficio, enviado_por, procedencia, asunto, pendiente, area)
                              VALUES ('2089-01-05','2089-01-01','Ana','Local','Enero',FALSE,'Sub. Jurídica')""")

    def setUp(self):
        self.client.force_login(self.user)

    def test_both_dates_are_required_on_server(self):
        from django.db import connection
        base = {'fecha_recibido':'2088-12-06', 'fecha_oficio':'2088-12-02', 'enviado_por':'Ana', 'procedencia':'Local', 'asunto':'Nuevo'}
        for field in ['fecha_recibido', 'fecha_oficio']:
            data = dict(base)
            data.pop(field)
            with self.assertLogs('documento.views', level='ERROR'):
                response = self.client.post('/oficios/ucg/2088/crear/', data)
            self.assertEqual(response.status_code, 302)
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM oficios_ucg_2088 WHERE asunto='Nuevo'")
            self.assertEqual(cursor.fetchone()[0], 0)
        response = self.client.post('/oficios/ucg/2088/crear/', base)
        self.assertEqual(response.status_code, 302)
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM oficios_ucg_2088 WHERE asunto='Nuevo'")
            self.assertEqual(cursor.fetchone()[0], 1)

    def test_edit_cannot_change_dates_even_if_posted(self):
        from datetime import date
        from django.db import connection
        response = self.client.post(f'/oficios/ucg/2088/{self.record_id}/editar/', {
            'asunto':'Editado','referencia':'','enviado_por':'Ana','procedencia':'Local',
            'fecha_recibido':'2088-10-01','fecha_oficio':'2088-10-01',
        })
        self.assertEqual(response.status_code, 302)
        with connection.cursor() as cursor:
            cursor.execute('SELECT fecha_recibido, fecha_oficio, asunto FROM oficios_ucg_2088 WHERE id=%s', [self.record_id])
            self.assertEqual(cursor.fetchone(), (date(2088,12,5), date(2088,12,1), 'Editado'))

    def test_selected_historical_months_and_empty_period(self):
        for month, label, pending in [('2088-12','diciembre de 2088',1), ('2089-01','enero de 2089',0)]:
            response = self.client.get('/inicio/', {'mes': month})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['current_month'], label)
            self.assertEqual(response.context['total_mes'], 1)
            self.assertEqual(response.context['pendientes_mes'], pending)
            self.assertIn(f'value="{month}"', response.content.decode())
        response = self.client.get('/inicio/', {'mes':'2089-02'})
        self.assertEqual(response.context['total_mes'], 0)
        self.assertIsNone(response.context['plot_areas'])
        self.assertIsNotNone(response.context['plot_nuevos'])
        empty = self.client.get('/inicio/', {'mes':'2087-01'})
        self.assertTrue(empty.context['no_data'])
        self.assertContains(empty, 'Mes siguiente')
