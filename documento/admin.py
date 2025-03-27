from django.contrib import admin
from django.db import connection

def tablas_existentes():
    with connection.cursor() as cursor:
        cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        return [row[0] for row in cursor.fetchall()]

# Registrar modelos dinámicos solo si existen las tablas
tablas = tablas_existentes()
for tabla in tablas:
    if tabla.startswith('oficios_ucg_'):
        anno = tabla.split('_')[-1]
        model_name = f'Oficios{anno}'
        
        try:
            model = getattr(__import__('documento.models', fromlist=[model_name]), model_name)
            admin.site.register(model)
        except AttributeError:
            pass