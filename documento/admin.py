from django.contrib import admin
from django.apps import apps
from django.db import connection, models, DatabaseError
import logging

logger = logging.getLogger(__name__)

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
            cls._registered = registrar_modelo_dinamico()

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

                model = apps.all_models.get('documento', {}).get(model_name.lower())
                if model is not None:
                    if not admin.site.is_registered(model):
                        admin.site.register(model, ModeloDinamicoAdmin)
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

    except DatabaseError:
        logger.exception("No se pudieron registrar los modelos dinámicos del administrador")
        return False
    return True

# Registrar antes de que Django recorra el registro para construir sus rutas.
# admin_view se invoca dentro de ese recorrido y no debe modificarlo.
if not hasattr(admin.site.__class__, '_original_get_urls'):
    admin.site.__class__._original_get_urls = admin.site.__class__.get_urls

    def patched_get_urls(self):
        LazyModelRegistry.register_all()
        return self._original_get_urls()

    admin.site.__class__.get_urls = patched_get_urls

from django.db.models.signals import post_migrate
from django.dispatch import receiver

@receiver(post_migrate)
def on_migrate(sender, **kwargs):
    if sender.name =='documento':
        LazyModelRegistry.register_all()