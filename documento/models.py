from tabnanny import verbose
from django.db import models

# Create your models here.
class Regsitro(models.Model):
    ASUNTO_OPCIONES = [
        ('atencion', 'Atención'),
        ('conocimiento', 'Conocimiento'),
        ('asistir', 'Asistir'),
        ('verme_antecedesntes', 'Verme con Antecedesntes'),
        ('opinion', 'Opinión'),
        ('respuesta', 'Respuesta'),
        ('archivo', 'Archivo'),
        ('urgente', 'Urgente'),
        ('analisis_validacion', 'Análisis para Validación'),
    ]
    AREA_OPCIONES = [
        ('direccion', 'Dirección General'),
        ('delegacion', 'Delegación Adminstracion'),
        ('ucg', 'Unidada de Control de Gestión'),
        ('juridica', 'Subdirección Jurídica'),
        ('planeacion', 'Subdirección de Planeación'),
        ('tecnia', 'Subdirección Técnica'),
        ('comercializacion', 'Subdirección de Comercialización'),
    ]

    folio = models.IntegerField(blank=True, null=True, verbose_name="Folio", unique=True)
    fehca_recibido = models.DateField(verbose_name="Fecha Recibido")
    fecha_oficio = models.DateField(verbose_name="Fecha Oficio")
    enviado_por = models.CharField(max_length=255, verbose_name="Enviado Por")
    procedencia = models.CharField(max_length=255, verbose_name="Procedencia")
    asunto = models.CharField(max_length=255, verbose_name="Asunto")
    referencia = models.CharField(max_length=255, verbose_name="Referencia")
    asunto_opciones = models.CharField(max_length=255, choices=ASUNTO_OPCIONES, verbose_name="Asunto Opciones")
    area = models.CharField(max_length=255, choices=AREA_OPCIONES, verbose_name="Área IVEM")
    pebdiente = models.BooleanField(verbose_name="Pendiente", default=False)
    archivo = models.FileField(upload_to='archivos/', blank=True, null=True, verbose_name="Archivo")

    def __str__(self):
        return f"Documento {self.folio} - {self.asunto}"