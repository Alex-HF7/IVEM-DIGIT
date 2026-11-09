from django.db import models, router, transaction
from django.core.exceptions import ValidationError

# Create your models here.
class ConfiguracionTable(models.Model):
    anno = models.IntegerField(unique=True, verbose_name="Año")
    descripcion = models.CharField(max_length=255, verbose_name="Descripción", blank=True, null=True)

    def clean(self):
        from .services import validate_year
        super().clean()
        validate_year(self.anno)
        if self.pk:
            previous = type(self).objects.using(self._state.db or 'default').filter(pk=self.pk).values_list('anno', flat=True).first()
            if previous is not None and previous != self.anno:
                raise ValidationError({'anno': 'El año no se puede cambiar. Crea otra configuración anual.'})

    def save(self, *args, **kwargs):
        using = kwargs.get('using') or router.db_for_write(type(self), instance=self)
        self.clean()
        # Incluye el post_save y las dos tablas en la misma transacción.
        with transaction.atomic(using=using):
            return super().save(*args, **kwargs)

    def __str__(self):
        return f"Tabla para el año {self.anno}"
    
    class Meta:
        verbose_name = "Configuración de Tabla"
        verbose_name_plural = "Configuración de Tablas"
        permissions = [
            ('view_all_documents', 'Consultar oficios de todos los departamentos'),
            ('view_pending_documents', 'Consultar el listado de pendientes'),
            ('assign_folio', 'Asignar folios a oficios'),
            ('delete_document', 'Eliminar oficios de forma lógica'),
            ('access_technical_admin', 'Acceder a la administración técnica Django'),
        ]
