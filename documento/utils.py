import os
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import connection, transaction

"""
    Obtiene registros de la tabla con filtros opcionales y ordenamiento.
"""
def getRegistros(tabla, filtros=None, order_by=None):    
    query = f"SELECT * FROM {tabla}"
    if filtros:
        condiciones = " AND ".join([f"{campo} = %s" for campo in filtros.keys()])
        query += f" WHERE {condiciones}"
    if order_by:
        query += f" ORDER BY {order_by}"
    with connection.cursor() as cursor:
        cursor.execute(query, list(filtros.values()) if filtros else [])
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

"""
    Guarda un archivo PDF para el oficio y actualiza la base de datos.
    Si ruta_anterior existe, elimina el archivo anterior.
"""
def saveArchivo(depto, year, id_oficio, archivo, ruta_anterior=None):
    # Crear directorio
    upload_dir = os.path.join(settings.MEDIA_ROOT, 'oficios', depto, str(year))
    os.makedirs(upload_dir, exist_ok=True)

    nombre_archivo = f"{id_oficio}_{depto}_{year}.pdf"
    ruta_completa = os.path.join(upload_dir, nombre_archivo)

    # Eliminar archivo anterior si existe
    if ruta_anterior and os.path.exists(os.path.join(settings.MEDIA_ROOT, ruta_anterior)):
        os.remove(os.path.join(settings.MEDIA_ROOT, ruta_anterior))

    # Guardar nuevo archivo
    fs = FileSystemStorage(location=upload_dir)
    nombre_guardado = fs.save(nombre_archivo, archivo)
    ruta_relativa = os.path.join('oficios', depto, str(year), nombre_guardado)

    # Actualizar base de datos
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE oficios_{depto}_{year} SET archivo = %s WHERE id = %s",
                [ruta_relativa, id_oficio]
            )
    return ruta_relativa

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
