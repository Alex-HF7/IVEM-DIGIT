from django.template.loader import render_to_string
from django.test import SimpleTestCase, override_settings
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
