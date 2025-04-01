from django.contrib import admin
from django.apps import apps
from django.db import connection, models

class ModeloDinamicoAdmin(admin.ModelAdmin):
    def __init__(self, model, admin_site):
        self.list_display= self.get_available_fields(model)
        super().__init__(model, admin_site)
    
    def get_available_fields(self, model):
        fields = []
        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = '{model._meta.db_table}'
            """)
            columns = [row[0] for row in cursor.fetchall()]
        
        for field in ['id', 'folio', 'fecha_recibido', 'enviado_por', 'asunto']:
            if field in columns:
                fields.append(field)
        
        return fields or ['__str__']
    
def registrar_modelo_dinamico():
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_name LIKE 'oficios\\_%\\_%'
                AND table_schema = 'public'
            """)

            for (table_name,) in cursor.fetchall():
                parts = table_name.split('_')
                if len(parts) !=3:
                    continue
                depto, year = parts[1], parts[2]
                model_name = f'Oficios{depto.capitalize()}{year}'

                if model_name in apps.all_models.get('documento',{}):
                    continue

                attrs = {
                    '__module__': 'documento.models',
                    '__str__': lambda self: f"{self._meta.verbose_name} {getattr(self, 'folio', '')}",
                    'Meta': type('Meta', (), {
                        'db_table': table_name,
                        'verbose_name': f'Oficio {depto} {year}',
                        'verbose_name_plural': f'Oficios {depto} {year}',
                    }),
                }

                with connection.cursor() as field_cursor:
                    field_cursor.execute(f"""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = '{table_name}'
                        AND column_name NOT IN ('id')
                    """)
                    for (column,) in field_cursor.fetchall():
                        attrs[column] = models.CharField(max_length=255, blank=True)
                
                model = type(model_name, (models.Model,), attrs)
                admin.site.register(model, ModeloDinamicoAdmin)
    except Exception as e:
        print(f"Error registrando modelos: {e}")

from django.contrib.admin import site as admin_site
if not admin_site.is_registered('documento'):
    registrar_modelo_dinamico()