from django.db.models.signals import post_save, post_migrate
from django.dispatch import receiver
from django.db import connection
from .models import ConfiguracionTable

@receiver(post_migrate)
def setup_dynamic_models(sender, **kwargs):
    if sender.name == 'gestion_tables':
        with connection.cursor() as cursor:
            cursor.execute("SELECT anno FROM gestion_tables_configuraciontable")
            for (year,) in cursor.fetchall():
                create_yearly_tables(year)

@receiver(post_save, sender=ConfiguracionTable)
def handle_config_save(sender, instance, created, **kwargs):
    if created:
        create_yearly_tables(instance.anno)

def create_yearly_tables(year):
    for depto in ['ucg', 'delegacion']:
        table_name = f'oficios_{depto}_{year}'
        
        # Crear secuencia primero
        create_depto_year_sequence(depto, year)
        
        # SQL para crear tabla + trigger
        sql = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id SERIAL PRIMARY KEY,
            folio INTEGER UNIQUE,
            fecha_recibido DATE NOT NULL,
            fecha_oficio DATE,
            enviado_por VARCHAR(255) NOT NULL,
            procedencia VARCHAR(255) NOT NULL,
            asunto VARCHAR(255) NOT NULL,
            referencia VARCHAR(255),
            asunto_opciones VARCHAR(255),
            area VARCHAR(255),
            pendiente BOOLEAN DEFAULT TRUE,
            archivo VARCHAR(255),
            departamento VARCHAR(20) DEFAULT '{depto}'
        );

        CREATE OR REPLACE FUNCTION set_folio_{depto}_{year}()
        RETURNS TRIGGER AS $$
        BEGIN
            IF NEW.pendiente = FALSE AND NEW.folio IS NULL THEN
                NEW.folio := nextval('folio_seq_{depto}_{year}');
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_trigger 
                WHERE tgname = 'trg_set_folio_{depto}_{year}'
            ) THEN
                EXECUTE format('
                    CREATE TRIGGER trg_set_folio_{depto}_{year}
                    BEFORE INSERT OR UPDATE ON %I
                    FOR EACH ROW EXECUTE FUNCTION set_folio_{depto}_{year}()',
                    '{table_name}'
                );
            END IF;
        END $$;
        """
        
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql)
        except Exception as e:
            print(f"Error al configurar {table_name}: {str(e)}")

def verify_tables():
    with connection.cursor() as cursor:
        cursor.execute("SELECT anno FROM gestion_tables_configuraciontable")
        for(anno,) in cursor.fetchall():
            create_yearly_tables(anno)

def create_depto_year_sequence(depto, year):
    """Crea una secuencia específica para cada departamento/año"""
    seq_name = f'folio_seq_{depto}_{year}'
    with connection.cursor() as cursor:
        cursor.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_sequences 
                    WHERE sequencename = '{seq_name}'
                ) THEN
                    EXECUTE 'CREATE SEQUENCE {seq_name} START 1';
                END IF;
            END $$;
        """)
