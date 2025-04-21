from django.db.models.signals import post_save, post_migrate
from django.dispatch import receiver
from django.db import connection
from .models import ConfiguracionTable

@receiver(post_migrate)
def setup_dynamic_models(sender, **kwargs):
    if sender.name == 'gestion_tables':
        verify_tables()

@receiver(post_save, sender=ConfiguracionTable)
def handle_config_save(sender, instance, created, **kwargs):
    if created:
        create_yearly_tables(instance.anno)

def create_yearly_tables(anno):      
    for depto in ['ucg', 'delegacion']:
        tabla_nombre = f'oficios_{depto}_{anno}'
        sql = f"""
        CREATE TABLE IF NOT EXISTS {tabla_nombre}(
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
        try:   
            # Verificar si la tabla ya existe
            with connection.cursor() as cursor:
                cursor.execute(sql)
        except Exception as e:
            print(f"Error al crear {tabla_nombre}: {e}")

def verify_tables():
    with connection.cursor() as cursor:
        cursor.execute("SELECT anno FROM gestion_tables_configuraciontable")
        for(anno,) in cursor.fetchall():
            create_yearly_tables(anno)