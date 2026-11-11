"""Pruebas con conexiones PostgreSQL reales y solicitudes simultáneas.

Django ejecuta estas operaciones exclusivamente en su base temporal de pruebas.
"""
from concurrent.futures import ThreadPoolExecutor
from django.contrib.auth import get_user_model
from django.db import connections, connection
from django.test import Client, TransactionTestCase
from .services import create_yearly_tables


class AuditConcurrencyTests(TransactionTestCase):
    year = 2093

    def worker(self, operation):
        connections.close_all()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SET statement_timeout TO '15s'")
                cursor.execute("SET lock_timeout TO '10s'")
            return operation()
        finally:
            connections.close_all()

    def tearDown(self):
        # Solo objetos del año reservado dentro de la base temporal de pruebas.
        with connection.cursor() as cursor:
            for department in ('ucg', 'delegacion'):
                cursor.execute(f'DROP TABLE IF EXISTS oficios_{department}_{self.year} CASCADE')
                cursor.execute(f'DROP FUNCTION IF EXISTS set_folio_{department}_{self.year}()')
                cursor.execute(f'DROP SEQUENCE IF EXISTS folio_seq_{department}_{self.year}')
        super().tearDown()

    def test_simultaneous_year_creation_is_idempotent(self):
        with ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(lambda _: self.worker(lambda: create_yearly_tables(self.year)), range(4)))
        with connection.cursor() as cursor:
            for department in ('ucg', 'delegacion'):
                cursor.execute('SELECT to_regclass(%s)', [f'oficios_{department}_{self.year}'])
                self.assertIsNotNone(cursor.fetchone()[0])
                cursor.execute(f'SELECT last_value, is_called FROM folio_seq_{department}_{self.year}')
                self.assertEqual(cursor.fetchone(), (1, False))

    def test_simultaneous_folio_requests_assign_once_without_sequence_growth(self):
        create_yearly_tables(self.year)
        user = get_user_model().objects.create_superuser(username='audit_concurrency', email='', password=None)
        with connection.cursor() as cursor:
            cursor.execute(f"""INSERT INTO oficios_ucg_{self.year}
                (fecha_recibido,fecha_oficio,enviado_por,procedencia,asunto)
                VALUES ('2093-01-02','2093-01-01','Auditoría','Pruebas','Concurrencia') RETURNING id""")
            identifier = cursor.fetchone()[0]

        def assign():
            client = Client()
            client.force_login(user)
            return client.post('/pendientes/asignar-folio/', {
                'tabla_origen': f'oficios_ucg_{self.year}', 'oficio_id': identifier,
                'asunto_opciones': 'conocimiento', 'area': 'Sub. Jurídica',
            }).status_code

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda _: self.worker(assign), range(4)))
        self.assertEqual(results, [302] * 4)
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT folio, pendiente FROM oficios_ucg_{self.year} WHERE id=%s', [identifier])
            self.assertEqual(cursor.fetchone(), (1, False))
            cursor.execute(f'SELECT last_value FROM folio_seq_ucg_{self.year}')
            self.assertEqual(cursor.fetchone()[0], 1)
