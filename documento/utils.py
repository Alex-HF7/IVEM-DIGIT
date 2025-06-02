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
