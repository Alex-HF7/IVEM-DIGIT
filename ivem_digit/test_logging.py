"""Verifica logging en un proceso aislado, sin alterar los loggers de la suite."""
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from django.conf import settings
from django.test import SimpleTestCase
from ivem_digit.logging_config import build_logging


class OperationalLoggingTests(SimpleTestCase):
    def test_console_preserves_errors_without_sql_and_no_default_log_file(self):
        self.assertNotIn('file', build_logging()['handlers'])
        script = '''
import logging, logging.config
from ivem_digit.logging_config import build_logging
logging.config.dictConfig(build_logging())
logging.getLogger('documento.views').error('OPERATIVE_ERROR')
logging.getLogger('django.request').warning('PUBLIC_ERROR')
for name in ['django.db', 'django.db.backends', 'django.db.backends.schema']:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.debug('PRIVATE_SQL_PARAMS')
    logger.error('PRIVATE_SQL_PARAMS')
'''
        result = subprocess.run([sys.executable, '-c', script], cwd=settings.BASE_DIR,
                                capture_output=True, text=True, check=True)
        self.assertIn('OPERATIVE_ERROR', result.stderr)
        self.assertIn('PUBLIC_ERROR', result.stderr)
        self.assertNotIn('PRIVATE_SQL_PARAMS', result.stderr + result.stdout)

    def test_optional_file_rotates_with_bounded_backups_and_no_sql(self):
        with TemporaryDirectory() as directory:
            target = Path(directory) / 'operational.log'
            config = build_logging(str(target))
            self.assertEqual(config['handlers']['file']['maxBytes'], 5 * 1024 * 1024)
            self.assertEqual(config['handlers']['file']['backupCount'], 5)
            script = '''
import logging, logging.config, sys
from ivem_digit.logging_config import build_logging
config=build_logging(sys.argv[1])
config['handlers']['file'].update(maxBytes=256, backupCount=2)
logging.config.dictConfig(config)
for i in range(20):
    logging.getLogger('documento.views').error('OPERATIVE_ERROR_' + str(i) + '_' * 100)
logging.getLogger('django.db.backends').error('PRIVATE_SQL_PARAMS')
logging.shutdown()
'''
            subprocess.run([sys.executable, '-c', script, str(target)], cwd=settings.BASE_DIR,
                           capture_output=True, text=True, check=True)
            files = list(Path(directory).glob('operational.log*'))
            self.assertEqual(len(files), 3)
            content = ''.join(path.read_text() for path in files)
            self.assertIn('OPERATIVE_ERROR_19', content)
            self.assertNotIn('PRIVATE_SQL_PARAMS', content)
