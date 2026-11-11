from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import connection, transaction

class DocumentConflict(Exception):
    pass


def validate_pdf(archivo):
    from pypdf import PdfReader
    from django.core.exceptions import ValidationError
    if not archivo or not archivo.name.lower().endswith('.pdf'):
        raise ValidationError('Selecciona un archivo PDF.')
    if archivo.size > settings.PDF_MAX_MB * 1024 * 1024:
        raise ValidationError(f'El PDF no puede superar {settings.PDF_MAX_MB} MB.')
    try:
        archivo.seek(0)
        reader = PdfReader(archivo, strict=True)
        if reader.is_encrypted or len(reader.pages) == 0:
            raise ValueError('PDF sin páginas accesibles')
    except Exception as error:
        raise ValidationError('El archivo no es un PDF válido o está protegido con contraseña.') from error
    finally:
        archivo.seek(0)


def saveArchivo(depto, year, id_oficio, archivo, ruta_anterior=None, action='upload'):
    """Conserva el PDF anterior hasta confirmar la nueva referencia en PostgreSQL."""
    import logging
    from pathlib import Path
    from uuid import uuid4
    from django.http import Http404
    from .access import table_name, record_id

    table = connection.ops.quote_name(table_name(depto, year))
    identifier = record_id(id_oficio)
    validate_pdf(archivo)
    if action not in {'upload', 'edit'}:
        raise DocumentConflict('Operación de archivo no válida.')
    storage = FileSystemStorage(location=settings.MEDIA_ROOT)
    saved = None
    try:
        with transaction.atomic(durable=True):
            with connection.cursor() as cursor:
                cursor.execute(f'SELECT archivo, pendiente, folio FROM {table} WHERE id=%s AND activo=TRUE FOR UPDATE', [identifier])
                row = cursor.fetchone()
                if not row:
                    raise Http404('Oficio no encontrado.')
                old, pending, folio = row
                if action == 'edit' and (not pending or folio is not None):
                    raise DocumentConflict('No se puede reemplazar el PDF de un oficio con folio asignado.')
                if action == 'upload' and old:
                    raise DocumentConflict('El oficio ya tiene un archivo. Actualiza el listado para reemplazarlo.')
                if action == 'edit' and not old:
                    raise DocumentConflict('El oficio no tiene un archivo para reemplazar.')
                name = f'oficios/{depto}/{int(year)}/{identifier}_{depto}_{int(year)}_{uuid4().hex}.pdf'
                saved = storage.save(name, archivo)
                cursor.execute(f'UPDATE {table} SET archivo=%s WHERE id=%s', [saved, identifier])
                if cursor.rowcount != 1:
                    raise DocumentConflict('No se pudo actualizar el archivo del oficio.')
                if old:
                    def delete_old():
                        try:
                            # Conserva archivos antiguos con rutas inseguras en vez de borrarlos.
                            safe_name = old.replace('\\', '/')
                            root = Path(settings.MEDIA_ROOT).resolve()
                            if Path(storage.path(safe_name)).resolve().is_relative_to(root):
                                storage.delete(safe_name)
                        except Exception:
                            logging.getLogger(__name__).exception('No se pudo limpiar el PDF anterior')
                    transaction.on_commit(delete_old)
        return saved
    except Exception:
        if saved:
            try:
                storage.delete(saved)
            except Exception:
                logging.getLogger(__name__).exception('No se pudo limpiar el PDF nuevo tras un fallo')
        raise


"""
    Paginador estándar para vistas.
"""
def paginar(request, items, per_page=20):
    page = request.GET.get('page', 1)
    paginator = Paginator(items, per_page)
    try:
        return paginator.page(page)
    except PageNotAnInteger:
        return paginator.page(1)
    except EmptyPage:
        return paginator.page(paginator.num_pages)


def buscar_oficios(request, tablas, pendientes=False, per_page=20):
    """Filtra, cuenta y pagina en PostgreSQL sin cargar el listado completo."""
    import re
    import unicodedata

    query = request.GET.get('q', '').strip()[:200]
    tokens = ''.join(char for char in unicodedata.normalize('NFKD', query.casefold())
                     if not unicodedata.combining(char)).split()
    selects, params = [], []
    for tabla in tablas:
        if not re.fullmatch(r'oficios_(ucg|delegacion)_\d{4}', tabla):
            raise ValueError('Tabla de oficios no válida')
        fields = "concat_ws(' ', id, folio, asunto, enviado_por, procedencia, referencia, area, departamento, to_char(fecha_recibido, 'DD/MM/YYYY'), to_char(fecha_oficio, 'DD/MM/YYYY'))"
        normalized = f"translate(lower({fields}), 'áéíóúüñ', 'aeiouun')"
        conditions = ['activo = TRUE']
        if pendientes:
            conditions.append('pendiente = TRUE')
        for token in tokens:
            conditions.append(f'{normalized} LIKE %s')
        selects.append(f"SELECT id, folio, fecha_recibido, fecha_oficio, enviado_por, procedencia, asunto, referencia, nota, asunto_opciones, area, activo, pendiente, archivo, departamento, %s AS tabla_origen FROM {connection.ops.quote_name(tabla)} WHERE " + ' AND '.join(conditions))
        params.append(tabla)
        params.extend('%' + connection.ops.prep_for_like_query(token) + '%' for token in tokens)
    if not selects:
        page = Paginator([], per_page).get_page(request.GET.get('page'))
    else:
        union = ' UNION ALL '.join(selects)
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT COUNT(*) FROM ({union}) AS oficios', params)
            total = cursor.fetchone()[0]
            page = Paginator(range(total), per_page).get_page(request.GET.get('page'))
            cursor.execute(f'SELECT * FROM ({union}) AS oficios ORDER BY fecha_recibido DESC, id DESC, tabla_origen LIMIT %s OFFSET %s',
                           params + [per_page, (page.number - 1) * per_page])
            columns = [column[0] for column in cursor.description]
            page.object_list = [dict(zip(columns, row)) for row in cursor.fetchall()]
    page.elided_page_range = list(page.paginator.get_elided_page_range(page.number, on_each_side=1, on_ends=1))
    return page, query
