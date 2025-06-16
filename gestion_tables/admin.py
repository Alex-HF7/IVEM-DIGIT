from django.contrib import admin
from .models import ConfiguracionTable
# Register your models here.
class GestionTablesAdmin(admin.ModelAdmin):
    list_display = ('anno', 'descripcion')
    search_fields = ('anno', 'descripcion')
    list_filter = ('anno',)
    ordering = ('-anno',)

admin.site.register(ConfiguracionTable, GestionTablesAdmin)