import logging
from django.contrib import admin, messages
from django.db import DatabaseError
from django.shortcuts import redirect
from .models import ConfiguracionTable
from .services import create_yearly_tables

logger = logging.getLogger(__name__)


@admin.register(ConfiguracionTable)
class GestionTablesAdmin(admin.ModelAdmin):
    list_display = ('anno', 'descripcion')
    search_fields = ('anno', 'descripcion')
    list_filter = ('anno',)
    ordering = ('-anno',)
    actions = ['verify_selected_years']

    def get_readonly_fields(self, request, obj=None):
        return ('anno',) if obj else ()

    def has_delete_permission(self, request, obj=None):
        # Eliminar la configuración no debe dejar tablas históricas huérfanas.
        return False

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except DatabaseError:
            logger.exception('No se pudo completar la configuración anual')
            self.message_user(request, 'No se pudo completar la creación de las tablas. No se guardaron cambios. Contacta al administrador o vuelve a intentarlo.', messages.ERROR)
            return redirect(request.path)

    @admin.action(description='Comprobar y completar las tablas de los años seleccionados', permissions=['change'])
    def verify_selected_years(self, request, queryset):
        for config in queryset:
            try:
                create_yearly_tables(config.anno, using=queryset.db)
                self.message_user(request, f'Año {config.anno}: tablas, secuencias y triggers comprobados.', messages.SUCCESS)
            except DatabaseError:
                logger.exception('Falló la comprobación anual')
                self.message_user(request, f'Año {config.anno}: no se pudo completar la comprobación. No se aplicaron cambios a ese año.', messages.ERROR)
