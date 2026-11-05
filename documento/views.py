import os
import logging
from django.conf import settings
from django.db import connection, transaction
from django.shortcuts import redirect, render
from django.contrib import messages
from datetime import datetime
from django.utils import timezone
from django.http import JsonResponse
from django.http import Http404
from .utils import saveArchivo, buscar_oficios

logger = logging.getLogger(__name__)
# Create your views here.
def years_disponibles():
    years = set()
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_name LIKE 'oficios\\_%\\_%'
        """)
        for (table_name,) in cursor.fetchall():
            parts = table_name.split('_')
            if len(parts) == 3:
                years.add(parts[2])
    return sorted(years, reverse=True)

def navbar_context(request):
    return {'years_disponibles': years_disponibles()}

def lista_oficios(request, depto, year):
    try:
        oficios, query = buscar_oficios(request, [f'oficios_{depto}_{year}'])
    except Exception:
        logger.exception('Error al consultar el listado de oficios')
        oficios, query = buscar_oficios(request, [])
        messages.error(request, 'No se pudo cargar el listado de oficios.')
    return render(request, 'documento/lista_oficios.html', {
        'oficios': oficios, 'depto': depto, 'year': year,
        'search_query': query, 'fecha_recibido_default': timezone.localdate(),
        'pdf_max_mb': settings.PDF_MAX_MB,
        'pdf_max_bytes': settings.PDF_MAX_MB * 1024 * 1024,
    })


def lista_pendientes(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name ~ '^oficios_(ucg|delegacion)_[0-9]{4}$'
                ORDER BY table_name
            """)
            tablas = [row[0] for row in cursor.fetchall()]
        oficios, query = buscar_oficios(request, tablas, pendientes=True)
    except Exception:
        logger.exception('Error al consultar oficios pendientes')
        oficios, query = buscar_oficios(request, [])
        messages.error(request, 'No se pudo cargar el listado de pendientes.')
    return render(request, 'documento/lista_pendientes.html', {
        'oficios': oficios, 'depto': 'todos', 'year': 'todos', 'search_query': query,
    })


def crear_oficio(request, depto, year):
    if request.method == 'POST':
        try:
            required_fields = ['fecha_recibido', 'fecha_oficio', 'enviado_por', 'procedencia', 'asunto']
            if not all(request.POST.get(field) for field in required_fields):
                raise ValueError("Faltan campos obligatorios")
            data = {
                'fecha_recibido': datetime.strptime(request.POST['fecha_recibido'], '%Y-%m-%d').date(),
                'fecha_oficio': datetime.strptime(request.POST['fecha_oficio'], '%Y-%m-%d').date(),
                'enviado_por': request.POST['enviado_por'],
                'procedencia': request.POST['procedencia'],
                'asunto': request.POST['asunto'],
                'referencia': request.POST.get('referencia', ''),
                'pendiente': True
            }                
            # Consulta SQL para insertar
            with transaction.atomic():
                with connection.cursor() as cursor:
                    columns = [k for k in data.keys() if data[k] is not None]
                    values = [data[k] for k in columns]
                    
                    cursor.execute(
                        f"""
                        INSERT INTO oficios_{depto}_{year} ({', '.join(columns)})
                        VALUES ({', '.join(['%s']*len(values))})
                        RETURNING id, folio;
                        """,
                        values
                    )
                    result = cursor.fetchone()
            
            msg = f"Oficio {f'n° {result[1]} ' if result[1] else ''}creado exitosamente"
            messages.success(request, msg)
            return redirect('lista_oficios', depto=depto, year=year)
            
        except Exception as e:
            messages.error(request, f"Error al crear oficio: {str(e)}")
            # Log detallado del error
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error al crear oficio: {str(e)}", exc_info=True)
            return redirect('lista_oficios', depto=depto, year=year)
    
    # Si no es POST, mostrar el formulario
    return render(request, 'lista_oficios.html', {
        'depto': depto,
        'year': year
    })

def grafica(request):
    from .dashboard import dashboard_period, dashboard_statistics

    period = dashboard_period(request.GET.get('mes'), timezone.localdate())
    if period['invalid_month']:
        messages.warning(request, 'El mes indicado no es válido. Se muestra el mes actual.')
    data = []
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name ~ '^oficios_(ucg|delegacion)_[0-9]{4}$'
                ORDER BY table_name
            """)
            tables = [row[0] for row in cursor.fetchall()]
            for table in tables:
                cursor.execute(f"""
                    SELECT fecha_recibido, pendiente, departamento, area
                    FROM {connection.ops.quote_name(table)}
                    WHERE fecha_recibido >= %s AND fecha_recibido < %s
                    ORDER BY fecha_recibido DESC
                """, [period['period_start'], period['period_end']])
                columns = [column[0] for column in cursor.description]
                data.extend(dict(zip(columns, row)) for row in cursor.fetchall())
        context = dashboard_statistics(data, period['selected_date'])
        if not context['no_data']:
            config = {'responsive': True, 'displayModeBar': False, 'scrollZoom': False}
            context['plot_nuevos'] = context.pop('fig_nuevos').to_html(
                full_html=False, include_plotlyjs='cdn', config=config)
            for figure_name, html_name in [('fig_pendientes', 'plot_pendientes'), ('fig_areas', 'plot_areas')]:
                figure = context.pop(figure_name)
                context[html_name] = figure.to_html(
                    full_html=False, include_plotlyjs=False, config=config) if figure is not None else None
    except Exception:
        logger.exception('No se pudieron generar las estadísticas de oficios')
        context = dashboard_statistics([], period['selected_date'])
        messages.error(request, 'No se pudieron cargar las estadísticas. Intenta nuevamente.')
    context.update(period)
    return render(request, 'documento/grafica.html', context)


def cargar_archivo(request):
    if request.method == 'POST':
        try:
            depto = request.POST.get('depto')
            year = request.POST.get('year')
            id_oficio = request.POST.get('id_oficio')
            if not all([depto, year, id_oficio]):
                return JsonResponse({'success': False, 'message': 'Faltan parámetros requeridos'}, status=400)

            if 'archivo' not in request.FILES:
                return JsonResponse({'success': False, 'message': 'No se ha seleccionado ningún archivo'}, status=400)

            archivo = request.FILES['archivo']
            if archivo.size > settings.PDF_MAX_MB * 1024 * 1024:
                return JsonResponse({'success': False, 'message': f'El PDF no puede superar {settings.PDF_MAX_MB} MB.'}, status=400)
            if not archivo.name.lower().endswith('.pdf'):
                return JsonResponse({'success': False, 'message': 'Tipo de archivo no permitido. Use PDF'}, status=400)

            ruta_relativa = saveArchivo(depto, year, id_oficio, archivo)
            return JsonResponse({
                'success': True,
                'message': 'Archivo cargado exitosamente',
                'file_url': os.path.join(settings.MEDIA_URL, ruta_relativa)
            })

        except Exception as e:
            logger.error(f"Error al cargar archivo: {str(e)}", exc_info=True)
            return JsonResponse({'success': False, 'message': f'Error al cargar archivo: {str(e)}'}, status=500)
    return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)

def asignar_folio(request):
    if request.method == 'POST':
        try:
            tabla_origen = request.POST.get('tabla_origen')
            oficio_id = request.POST.get('oficio_id')
            asunto_opciones = request.POST.get('asunto_opciones')
            area = request.POST.get('area')
            nota = request.POST.get('nota')

            if not all([tabla_origen, oficio_id, asunto_opciones, area]):
                raise ValueError("Todos los campos son obligatorios")

            # Extraer departamento y año del nombre de la tabla
            partes = tabla_origen.split('_')
            if len(partes) != 3:
                raise ValueError("Formato de tabla inválido")
            
            depto = partes[1]
            year = partes[2]

            with transaction.atomic():
                with connection.cursor() as cursor:
                    # Verificar que el registro sigue siendo pendiente
                    cursor.execute(f"""
                        SELECT pendiente FROM {tabla_origen} 
                        WHERE id = %s FOR UPDATE
                    """, [oficio_id])
                    
                    resultado = cursor.fetchone()
                    if not resultado or not resultado[0]:
                        raise ValueError("El oficio ya no está pendiente")
                    
                    # Asignar folio y actualizar campos
                    cursor.execute(f"""
                        UPDATE {tabla_origen}
                        SET 
                            pendiente = FALSE,
                            folio = nextval('folio_seq_{depto}_{year}'),
                            asunto_opciones = %s,
                            area = %s,
                            nota = %s
                        WHERE id = %s
                        RETURNING folio;
                    """, [asunto_opciones, area, nota, oficio_id])
                    
                    folio = cursor.fetchone()[0]
                    messages.success(request, f"Folio {folio} asignado correctamente al oficio {oficio_id}")

        except Exception as e:
            messages.error(request, f"Error al asignar folio: {str(e)}")
            logger.error(f"Error asignando folio a {tabla_origen}/{oficio_id}: {str(e)}", exc_info=True)
    
    return redirect('lista_pendientes')

def imprimir_oficio(request, depto, year, record_id):
    tabla = f'oficios_{depto}_{year}'
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT * FROM {tabla} WHERE id = %s", [record_id])
            row = cursor.fetchone()
            if not row:
                raise Http404("Oficio no encontrado")
            columnas = [col[0] for col in cursor.description]
            data = dict(zip(columnas, row))
    except Exception as e:
        raise Http404(f"Error al acceder a la tabla: {e}")

    return render(request, 'documento/formato_oficio.html', {'data': data})

def eliminar_oficio(request, depto, year, id):
    tabla = f'oficios_{depto}_{year}'
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"""
                    UPDATE {tabla} SET activo = FALSE WHERE id = %s
                """, [id])
        messages.success(request, "El oficio fue eliminado correctamente.")
    except Exception as e:
        messages.error(request, f"Error al eliminar oficio: {str(e)}")
    return redirect('lista_oficios', depto=depto, year=year) 

def editar_oficio(request, depto, year, id):
    tabla = f'oficios_{depto}_{year}'
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT * FROM {tabla} WHERE id = %s", [id])
            columns = [col[0] for col in cursor.description]
            row = cursor.fetchone()
        if not row:
            messages.error(request, "Oficio no encontrado.")
            return redirect('lista_oficios', depto=depto, year=year)
        data = dict(zip(columns, row))
    except Exception as e:
        messages.error(request, f"Error al obtener oficio: {str(e)}")
        return redirect('lista_oficios', depto=depto, year=year)

    if request.method == 'POST':
        try:
            asunto = request.POST.get('asunto')
            referencia = request.POST.get('referencia')
            enviado_por = request.POST.get('enviado_por')
            procedencia = request.POST.get('procedencia')

            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(f"""
                        UPDATE {tabla}
                        SET asunto = %s,
                            referencia = %s,
                            enviado_por = %s,
                            procedencia = %s
                        WHERE id = %s
                    """, [
                        asunto,
                        referencia,
                        enviado_por,
                        procedencia,
                        id
                    ])
            messages.success(request, "El oficio fue actualizado correctamente.")
            return redirect('lista_oficios', depto=depto, year=year)
        except Exception as e:
            messages.error(request, f"Error al actualizar oficio: {str(e)}")
            return redirect('editar_oficio', depto=depto, year=year, id=id)

    return render(request, 'documento/editar_oficio.html', {
        'data': data,
        'depto': depto,
        'year': year
    })

def archivo(request):
    if request.method == 'POST':
        try:
            depto = request.POST.get('depto')
            year = request.POST.get('year')
            id_oficio = request.POST.get('id_oficio')
            action = request.POST.get('action', 'upload')
            if not all([depto, year, id_oficio]):
                return JsonResponse({'success': False, 'message': 'Faltan parámetros requeridos'}, status=400)

            if 'archivo' not in request.FILES:
                return JsonResponse({'success': False, 'message': 'No se ha seleccionado ningún archivo'}, status=400)

            archivo = request.FILES['archivo']
            if archivo.size > settings.PDF_MAX_MB * 1024 * 1024:
                return JsonResponse({'success': False, 'message': f'El PDF no puede superar {settings.PDF_MAX_MB} MB.'}, status=400)
            if not archivo.name.lower().endswith('.pdf'):
                return JsonResponse({'success': False, 'message': 'Tipo de archivo no permitido. Solo PDF'}, status=400)

            if action == 'edit':
                with connection.cursor() as cursor:
                    cursor.execute(
                        f"SELECT archivo FROM oficios_{depto}_{year} WHERE id = %s",
                        [id_oficio]
                    )
                    resultado = cursor.fetchone()
                    ruta_actual = resultado[0] if resultado and resultado[0] else None
            else:
                ruta_actual = None

            ruta_relativa = saveArchivo(depto, year, id_oficio, archivo, ruta_anterior=ruta_actual)
            messages.success(request, 'Archivo actualizado exitosamente' if action == 'edit' else 'Archivo cargado exitosamente')
            return JsonResponse({
                'success': True,
                'message': 'Archivo guardado exitosamente',
                'file_url': os.path.join(settings.MEDIA_URL, ruta_relativa)
            })

        except Exception as e:
            logger.error(f"Error al procesar archivo: {str(e)}", exc_info=True)
            return JsonResponse({'success': False, 'message': f'Error al procesar archivo: {str(e)}'}, status=500)
    return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)