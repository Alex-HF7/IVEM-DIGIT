from django.contrib import admin
from django.db import connection
from importlib import import_module
from gestion_tables.models import ConfiguracionTable

def get_dynamic_model(anno):
    """Crea dinámicamente la clase Model para el anno especificado"""
    from documento.models import Oficio  # Modelo abstracto base
    
    attrs = {
        '__module__': 'documento.models',
        'Meta': type('Meta', (), {
            'db_table': f'oficios_ucg_{anno}',
            'verbose_name': f'Oficio {anno}',
            'verbose_name_plural': f'Oficios {anno}',
        }),
    }
    
    return type(f'Oficios{anno}', (Oficio,), attrs)


class DynamicModelAdmin(admin.ModelAdmin):
    """Clase base para administrar los modelos dinámicos"""
    list_display = ('folio', 'enviado_por', 'asunto')
    search_fields = ('folio', 'enviado_por', 'asunto')

# Registrar modelos dinámicos para cada anno existente
try:
    for config in ConfiguracionTable.objects.all():
        anno = config.anno
        try:
            model = get_dynamic_model(anno)
            admin.site.register(model, DynamicModelAdmin)
        except Exception as e:
            print(f"No se pudo registrar modelo para el anno {anno}: {e}")
except Exception as e:
    print(f"Error al registrar modelos dinámicos: {e}")

