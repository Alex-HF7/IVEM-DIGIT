from django.contrib import admin
from django.apps import apps
from django.db import connection

# Cache para evitar registro duplicado
_registered_models = set()

class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ('folio', 'enviado_por', 'asunto')
    search_fields = ('folio', 'enviado_por')

def register_dynamic_models():
    global _registered_models
    
    # Verificar si ya estamos en fase de inicialización
    if not apps.ready:
        return

    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_name LIKE 'oficios\\_%\\_%'
            """)
            
            for (table_name,) in cursor.fetchall():
                if table_name in _registered_models:
                    continue
                    
                parts = table_name.split('_')
                if len(parts) != 3:
                    continue
                    
                depto, year = parts[1], parts[2]
                model_name = f'Oficios{depto.capitalize()}{year}'
                
                # Crear modelo dinámico
                model = type(
                    model_name,
                    (models.Model,),
                    {
                        '__module__': 'documento.models',
                        'Meta': type('Meta', (), {
                            'db_table': table_name,
                            'app_label': 'documento',
                        }),
                    }
                )
                
                # Registrar solo si no existe
                if not apps.is_installed('documento') or model_name not in apps.all_models['documento']:
                    admin.site.register(model, DepartamentoAdmin)
                    _registered_models.add(table_name)
                    
    except Exception as e:
        print(f"Error registrando modelos: {e}")

# Conectar a señal post_migrate
from django.core.signals import request_started
from django.dispatch import receiver

@receiver(request_started)
def on_request_started(sender, **kwargs):
    register_dynamic_models()
