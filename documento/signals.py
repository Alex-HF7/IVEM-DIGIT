from django.db.models.signals import post_save
from django.dispatch import receiver
from gestion_tables.models import ConfiguracionTable
from documento.models import Oficio

@receiver(post_save, sender=ConfiguracionTable)
def crearModuloDinamico(sender, instance, created, **kwargs):
    if created:
        anno = instance.anno
        nuevoModel = type(
            f"Oficios{anno}", 
            (Oficio,), 
            {
                '__module__': 'documento.models',
                'Meta': type('Meta', (), {'db_table': f"oficios_ucg_{anno}"}),
            }
        )