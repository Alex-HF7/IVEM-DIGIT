from tabnanny import verbose
from django.db import models

# Create your models here.
class ConfiguracionTable(models.Model):
    anno = models.IntegerField(unique=True, verbose_name="Año")
    descripcion = models.CharField(max_length=255, verbose_name="Descripción", blank=True, null=True)

    def __str__(self):
        return f"Tabla para el ao {selft.anno}"
    
    class Meta:
        verbose_name = "Configuración de Tabla"
        verbose_name_plural = "Configuración de Tablas"