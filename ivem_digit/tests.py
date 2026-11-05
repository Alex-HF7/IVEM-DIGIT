from unittest.mock import patch
from django.test import SimpleTestCase, Client, override_settings
from django.urls import get_script_prefix, set_script_prefix
from .errors import error_response
from .test_error_urls import SECRET


@override_settings(DEBUG=False, ROOT_URLCONF='ivem_digit.test_error_urls')
class PublicErrorTests(SimpleTestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)

    def assert_safe_page(self, response, status):
        self.assertEqual(response.status_code, status)
        html = response.content.decode()
        self.assertIn(f'<span class="code">{status}</span>', html)
        for private in [SECRET, 'urlpatterns', 'Traceback', 'Using the URLconf', 'DEBUG =', 'Request Method:']:
            self.assertNotIn(private, html)
        self.assertIn('prefers-reduced-motion', html)
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_unknown_route_and_common_exceptions_are_safe(self):
        self.assert_safe_page(self.client.get('/unknown-private-path/'), 404)
        for status in [400,403,404,500]:
            with self.subTest(status=status):
                self.assert_safe_page(self.client.get(f'/raise/{status}/'), status)

    def test_method_errors_preserve_allow_and_do_not_expose_internal_content(self):
        response = self.client.get('/post/')
        self.assert_safe_page(response, 405)
        self.assertEqual(response['Allow'], 'POST')
        response = self.client.get('/unavailable/')
        self.assert_safe_page(response, 503)
        self.assertEqual(response['Retry-After'], '30')

    def test_csrf_failure_hides_the_internal_reason(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post('/post/', {})
        self.assert_safe_page(response,403)
        self.assertIn('Actualiza la página', response.content.decode())
        self.assertNotIn('CSRF cookie not set', response.content.decode())

    def test_ajax_errors_use_generic_json_and_existing_json_remains_usable(self):
        response = self.client.get('/raise/500/', HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code,500)
        self.assertFalse(response.json()['success'])
        self.assertNotIn(SECRET, response.content.decode())
        response = self.client.get('/unknown/', HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code,404)
        self.assertEqual(response.json()['status'],404)
        response = self.client.get('/json/')
        self.assertEqual(response.json()['message'], 'Selecciona un PDF válido.')

    def test_error_page_does_not_run_database_context_processors_or_expose_path(self):
        from django.test import RequestFactory
        request = RequestFactory().get('/' + SECRET)
        with patch('documento.views.navbar_context', side_effect=AssertionError('Context processor must not run')):
            response = error_response(request,500)
        self.assert_safe_page(response,500)
        self.assertNotIn('cdn.', response.content.decode())

    def test_home_link_respects_deployment_prefix(self):
        from django.test import RequestFactory
        previous = get_script_prefix()
        try:
            set_script_prefix('/ivem/')
            response = error_response(RequestFactory().get('/unknown/'),404)
            self.assertIn('href="/ivem/"', response.content.decode())
        finally:
            set_script_prefix(previous)

    @override_settings(DEBUG=True)
    def test_middleware_also_hides_technical_pages_if_debug_is_enabled_accidentally(self):
        self.assert_safe_page(self.client.get('/unknown/'),404)
        self.assert_safe_page(self.client.get('/raise/500/'),500)

    @override_settings(ROOT_URLCONF='ivem_digit.urls')
    def test_real_unknown_route_uses_public_error_page(self):
        response = self.client.get('/swagger/')
        self.assert_safe_page(response,404)
        self.assertNotIn('manejar-archivo', response.content.decode())
