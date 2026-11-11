"""Consulta de tablas anuales sin incorporarlas al esquema gestionado por migraciones."""
import logging
from threading import RLock
from django.apps import apps
from django.apps.registry import Apps
from django.contrib import admin
from django.db import DatabaseError, models
from django.http import Http404
from django.urls import path, re_path, reverse
from .access import available_tables, parse_table, require_document_permission, has_document_permission, table_name
from .models import Oficio

logger = logging.getLogger(__name__)
# Registro separado: las tablas las crea gestion_tables, no makemigrations.
dynamic_apps = Apps(installed_apps=[])
registry_lock = RLock()


class ModeloDinamicoAdmin(admin.ModelAdmin):
    list_display = ('id', 'folio', 'fecha_recibido', 'enviado_por', 'asunto', 'pendiente')
    list_display_links = None
    ordering = ('-fecha_recibido', '-id')
    list_filter = ('pendiente', 'activo')
    search_fields = ('asunto', 'enviado_por', 'procedencia', 'referencia')
    actions = None

    def has_view_permission(self, request, obj=None):
        return has_document_permission(request.user, 'view_all_documents')

    def has_module_permission(self, request):
        return self.has_view_permission(request)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)


class LazyModelRegistry:
    _registered = False

    @classmethod
    def register_all(cls, force=False):
        if apps.ready and (force or not cls._registered):
            with registry_lock:
                cls._registered = registrar_modelo_dinamico()


def registrar_modelo_dinamico():
    try:
        tables = set(available_tables({'ucg', 'delegacion'}))
        registry = dynamic_apps.all_models['documento']
        for key, model in list(registry.items()):
            if model._meta.db_table not in tables:
                if admin.site.is_registered(model):
                    admin.site.unregister(model)
                del registry[key]
        for table in sorted(tables):
            depto, year = parse_table(table)
            name = f'Oficios{depto.capitalize()}{year}'
            model = registry.get(name.lower())
            if model is None:
                model = type(name, (Oficio,), {
                    '__module__': 'documento.models',
                    # Compatibilidad con la errata del modelo abstracto original.
                    'fehca_recibido': None,
                    'fecha_recibido': models.DateField(verbose_name='Fecha recibido'),
                    'departamento': models.CharField(max_length=20),
                    'Meta': type('Meta', (), {
                        'app_label': 'documento', 'apps': dynamic_apps, 'managed': False,
                        'db_table': table, 'verbose_name': f'Oficio {depto} {year}',
                        'verbose_name_plural': f'Oficios {depto} {year}',
                    }),
                })
            if not admin.site.is_registered(model):
                admin.site.register(model, ModeloDinamicoAdmin)
        return True
    except DatabaseError:
        logger.exception('No se pudieron registrar las tablas anuales para consulta')
        return False


def annual_documents(request, depto, year):
    require_document_permission(request.user, 'view_all_documents')
    table = table_name(depto, year)
    LazyModelRegistry.register_all(force=True)
    model = dynamic_apps.all_models['documento'].get(f'oficios{depto}{year}'.lower())
    if model is None or model._meta.db_table != table:
        raise Http404('Año no disponible.')
    return admin.site._registry[model].changelist_view(request)


site_class = admin.site.__class__
if not hasattr(site_class, '_original_get_urls'):
    site_class._original_get_urls = site_class.get_urls

    def patched_get_urls(self):
        with registry_lock:
            LazyModelRegistry.register_all()
            return [
                path('documento/anuales/<str:depto>/<int:year>/', self.admin_view(annual_documents), name='annual_documents'),
                re_path(r'^(?P<app_label>documento)/$', self.admin_view(self.app_index), name='app_list'),
            ] + self._original_get_urls()

    site_class.get_urls = patched_get_urls

if not hasattr(site_class, '_original_get_app_list'):
    site_class._original_get_app_list = site_class.get_app_list

    def patched_get_app_list(self, request, app_label=None):
        # Fuera del recorrido interno de Django: evita mutar el registro durante ese recorrido.
        LazyModelRegistry.register_all(force=True)
        with registry_lock:
            result = self._original_get_app_list(request, app_label)
        for app in result:
            for entry in app['models']:
                model = entry.get('model')
                if model is not None and model._meta.apps is dynamic_apps:
                    depto, year = parse_table(model._meta.db_table)
                    entry['admin_url'] = reverse('admin:annual_documents', kwargs={'depto': depto, 'year': year})
        return result

    site_class.get_app_list = patched_get_app_list
