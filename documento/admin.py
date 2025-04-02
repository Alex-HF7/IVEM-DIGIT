from django.contrib import admin
from django.apps import apps
from django.db import connection, models

class ModeloDinamicoAdmin(admin.ModelAdmin):
    def __init__(self, model, admin_site):
        self.list_display= self.get_available_fields(model)
        super().__init__(model, admin_site)
    
    def get_available_fields(self, model):
        
        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = '{model._meta.db_table}'
            """)
            columns = [row[0] for row in cursor.fetchall()]
        
        for field in ['id', 'folio', 'fecha_recibido', 'enviado_por', 'asunto']:
            if field in columns:
                return [field]
        return ['__str__']
class LazyModelRegistry:
    _registered = False

    @classmethod
    def register_all(cls):
        if not cls._registered and apps.ready:
            cls._registered=True
            registrar_modelo_dinamico()

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
                    #'__str__': lambda self: f"{self._meta.verbose_name} {getattr(self, 'folio', '')}",
                    'Meta': type('Meta', (), {
                        'db_table': table_name,
                        'verbose_name': f'Oficio {depto} {year}',
                        'verbose_name_plural': f'Oficios {depto} {year}',
                    }),
                }

                model = type(model_name, (models.Model,), attrs)
                admin.site.register(model, ModeloDinamicoAdmin)

    except Exception as e:
        print(f"Error registrando modelos: {e}")

if not hasattr(admin.site.__class__, '_original_admin_view'):
    admin.site.__class__._original_admin_view = admin.site.__class__.admin_view
    
    def patched_admin_view(self, view, cacheable=False):
        LazyModelRegistry.register_all()
        return self._original_admin_view(view, cacheable)
    
    admin.site.__class__.admin_view = patched_admin_view

from django.db.models.signals import post_migrate
from django.dispatch import receiver

@receiver(post_migrate)
def on_migrate(sender, **kwargs):
    if sender.name =='documento':
        LazyModelRegistry.register_all()