from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import connection
from .models import ConfiguracionTable

@receiver(post_save, sender=ConfiguracionTable)
def crear_tablas_dinamicas(sender, instance, created, **kwargs):
    if created:
        anno = instance.anno
        
        # Lista de departamentos a crear
        departamentos = ['ucg', 'delegacion']
        
        for depto in departamentos:
            tabla_nombre = f'oficios_{depto}_{anno}'
            
            # Verificar si la tabla ya existe
            with connection.cursor() as cursor:
                cursor.execute(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = '{tabla_nombre}'
                    );
                """)
                existe = cursor.fetchone()[0]
            
            if not existe:
                try:
                    # SQL para crear la tabla con todos los campos
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
                        archivo VARCHAR(255),
                        departamento VARCHAR(20) DEFAULT '{depto}'
                    );
                    """
                    
                    with connection.cursor() as cursor:
                        cursor.execute(sql)
                    print(f"Tabla {tabla_nombre} creada exitosamente!")
                except Exception as e:
                    print(f"Error al crear {tabla_nombre}: {e}")