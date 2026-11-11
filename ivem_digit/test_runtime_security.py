from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import secrets
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from django.core.exceptions import DisallowedHost
from django.test import SimpleTestCase, override_settings
from .runtime_security import validate_secret, allowed_hosts, development_secret


class RuntimeSecurityTests(SimpleTestCase):
    def test_secret_requires_private_non_default_value_without_echoing_it(self):
        for value in ['', 'short', 'a' * 64, 'django-insecure-' + secrets.token_urlsafe(50)]:
            with self.subTest(kind=len(value)):
                with self.assertRaises(ImproperlyConfigured) as error:
                    validate_secret(value)
                if value:
                    self.assertNotIn(value, str(error.exception))
        strong = secrets.token_urlsafe(64)
        self.assertEqual(validate_secret(strong), strong)

    def test_hosts_accept_exact_ip_and_names_but_no_wildcards_urls_or_ports(self):
        self.assertEqual(allowed_hosts('203.0.113.10,IVEM.example.com, [::1],203.0.113.10'),
                         ['203.0.113.10', 'ivem.example.com', '[::1]'])
        for value in ['', '*', '*.example.com', '.example.com', 'https://example.com',
                      '[127.0.0.1]', '[::1', '[[::1]]', 'example.com:8000', 'example.com/path', 'bad..name', '999.999.999.999', '-bad.com']:
            with self.subTest(value=value), self.assertRaises(ImproperlyConfigured):
                allowed_hosts(value)

    def test_unlisted_host_is_rejected_by_django(self):
        request = HttpRequest()
        request.META['HTTP_HOST'] = 'attacker.example'
        with override_settings(ALLOWED_HOSTS=allowed_hosts('203.0.113.10')):
            with self.assertRaises(DisallowedHost):
                request.get_host()
            request.META['HTTP_HOST'] = '203.0.113.10:8000'
            self.assertEqual(request.get_host(), '203.0.113.10:8000')

    @patch.dict(os.environ, {'IVEM_SECRET_KEY': ''})
    def test_local_key_is_private_persistent_and_shared_by_concurrent_startups(self):
        with TemporaryDirectory() as directory:
            with ThreadPoolExecutor(max_workers=4) as executor:
                keys = list(executor.map(lambda _: development_secret(directory), range(4)))
            self.assertEqual(len(set(keys)), 1)
            self.assertEqual(development_secret(directory), keys[0])
            self.assertGreaterEqual(len(keys[0]), 50)
            path = Path(directory) / 'secret-key'
            if os.name != 'nt':
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            path.write_text('invalid', encoding='utf-8')
            with self.assertRaises(ImproperlyConfigured):
                development_secret(directory)
            self.assertEqual(path.read_text(), 'invalid')

    def test_server_settings_require_explicit_configuration(self):
        # Importa configuración en procesos aislados para no cambiar la suite.
        env = os.environ.copy()
        env.update(IVEM_SECRET_KEY='', IVEM_ALLOWED_HOSTS='', PYTHON_DOTENV_DISABLED='1')
        command = [sys.executable, '-c', 'import ivem_digit.settings']
        result = subprocess.run(command, env=env, cwd=settings.BASE_DIR, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('IVEM_SECRET_KEY', result.stderr)
        env['IVEM_SECRET_KEY'] = secrets.token_urlsafe(64)
        result = subprocess.run(command, env=env, cwd=settings.BASE_DIR, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('IVEM_ALLOWED_HOSTS', result.stderr)
        env['IVEM_ALLOWED_HOSTS'] = '203.0.113.10'
        result = subprocess.run(command, env=env, cwd=settings.BASE_DIR, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
