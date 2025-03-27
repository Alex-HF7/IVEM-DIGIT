from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import connection
from .models import ConfiguracionTable

@receiver(post_save, sender=ConfiguracionTable)
def crear_tabla_dinamica(sender, instance, created, **kwargs):
    if created:
        anno = instance.anno
        tabla_nombre = f'oficios_ucg_{anno}'
        
        # SQL para crear la tabla con todos los campos necesarios
        sql = f"""
        CREATE TABLE {tabla_nombre} (
            id SERIAL PRIMARY KEY,
            folio INTEGER,
            fecha_recibido DATE,
            fecha_oficio DATE,
            enviado_por VARCHAR(255),
            procedencia VARCHAR(255),
            asunto VARCHAR(255),
            referencia VARCHAR(255),
            asunto_opciones VARCHAR(255),
            area VARCHAR(255),
            pendiente BOOLEAN DEFAULT FALSE,
            archivo VARCHAR(255)
        );
        """
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql)
            print(f"Tabla {tabla_nombre} creada exitosamente!")
        except Exception as e:
            print(f"Error al crear tabla {tabla_nombre}: {e}")