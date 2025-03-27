from django.contrib import admin

# Register your models here.
class DocumentoAdmin(admin.ModelAdmin):
    list_display = ('folio', 'fehca_recibido', 'fecha_oficio', 'enviado_por', 'procedencia', 'asunto', 'referencia', 'asunto_opciones', 'area', 'pendiente', 'archivo')
    search_fields = ('folio', 'enviado_por', 'procedencia', 'asunto', 'referencia', 'asunto_opciones', 'area', 'pendiente')
    list_filter = ('fehca_recibido', 'fecha_oficio', 'asunto_opciones', 'area', 'pendiente')
    date_hierarchy = 'fehca_recibido'
    ordering = ('-fehca_recibido',)
