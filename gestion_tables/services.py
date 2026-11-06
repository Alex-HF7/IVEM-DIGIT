"""Creación anual transaccional; nunca elimina tablas ni reinicia secuencias existentes."""
from django.core.exceptions import ValidationError
from django.db import connections, transaction, DatabaseError


def validate_year(year):
    if isinstance(year, bool) or not str(year).isdigit() or not 1000 <= int(year) <= 9999:
        raise ValidationError({'anno': 'Indica un año de cuatro dígitos (1000–9999).'})
    return int(year)


def create_yearly_tables(year, using='default'):
    year = validate_year(year)
    connection = connections[using]
    if connection.vendor != 'postgresql':
        raise DatabaseError('La creación de tablas anuales requiere PostgreSQL.')
    with transaction.atomic(using=using):
        with connection.cursor() as cursor:
            # Serializa solicitudes simultáneas para el mismo año.
            cursor.execute('SELECT pg_advisory_xact_lock(%s, %s)', [492011, year])
            cursor.execute('SET LOCAL search_path TO public')
        _create_yearly_tables(year, connection)


def _create_yearly_tables(year, connection):
    for depto in ['ucg', 'delegacion']:
        table_name = f'oficios_{depto}_{year}'
        
        # Crear secuencia primero
        seq_name = f'folio_seq_{depto}_{year}'
        with connection.cursor() as cursor:
            cursor.execute('SELECT to_regclass(%s)', [f'public.{seq_name}'])
            sequence_existed = cursor.fetchone()[0] is not None
            cursor.execute(f'CREATE SEQUENCE IF NOT EXISTS "public"."{seq_name}" START 1')
        
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
            nota VARCHAR(255),
            asunto_opciones VARCHAR(255),
            area VARCHAR(255),
            activo BOOLEAN DEFAULT TRUE,
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
                  AND tgrelid = 'public.{table_name}'::regclass
                  AND NOT tgisinternal
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
        
        with connection.cursor() as cursor:
            cursor.execute(sql)
            cursor.execute("""SELECT column_name FROM information_schema.columns
                              WHERE table_schema='public' AND table_name=%s""", [table_name])
            columns = {row[0] for row in cursor.fetchall()}
            required = {'id', 'folio', 'fecha_recibido', 'fecha_oficio', 'enviado_por',
                        'procedencia', 'asunto', 'referencia', 'nota', 'asunto_opciones',
                        'area', 'activo', 'pendiente', 'archivo', 'departamento'}
            if not required.issubset(columns):
                raise DatabaseError(f'La tabla {table_name} requiere revisión de su estructura.')
            cursor.execute("""SELECT EXISTS (
                SELECT 1 FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname=%s
                AND tgfoid=to_regprocedure(%s) AND tgenabled IN ('O','A') AND NOT tgisinternal
            )""", [f'public.{table_name}', f'trg_set_folio_{depto}_{year}', f'public.set_folio_{depto}_{year}()'])
            if not cursor.fetchone()[0]:
                raise DatabaseError(f'El trigger de {table_name} requiere revisión.')
            if sequence_existed:
                cursor.execute(f'SELECT last_value, is_called FROM "public"."{seq_name}"')
                last, called = cursor.fetchone()
                cursor.execute(f'SELECT COALESCE(MAX(folio), 0) FROM "public"."{table_name}"')
                if (last + 1 if called else last) <= cursor.fetchone()[0]:
                    raise DatabaseError(f'La secuencia {seq_name} requiere revisión; no se reinició.')
            if not sequence_existed:
                # Recuperar una secuencia ausente sin repetir folios ya existentes.
                cursor.execute(f'SELECT COALESCE(MAX(folio), 0) + 1 FROM "public"."{table_name}"')
                cursor.execute('SELECT setval(%s::regclass, %s, FALSE)', [f'public.{seq_name}', cursor.fetchone()[0]])
