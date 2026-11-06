import logging
from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.files.storage import default_storage
from django.db import connection, transaction, DatabaseError
from django.http import JsonResponse, Http404, FileResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_http_methods
from .access import (allowed_departments, available_tables, parse_table, record_id,
                     require_admin, require_department)
from .forms import DocumentCreateForm, DocumentEditForm, FolioForm, error_message
from .utils import saveArchivo, buscar_oficios, DocumentConflict

logger = logging.getLogger(__name__)


def years_disponibles(user):
    return sorted({str(parse_table(table)[1]) for table in available_tables(allowed_departments(user))}, reverse=True)


def navbar_context(request):
    return {'years_disponibles': years_disponibles(request.user)}


def lista_oficios(request, depto, year):
    table = require_department(request.user, depto, year)
    try:
        oficios, query = buscar_oficios(request, [table])
    except DatabaseError:
        logger.exception('Error al consultar el listado de oficios')
        oficios, query = buscar_oficios(request, [])
        messages.error(request, 'No se pudo cargar el listado de oficios.')
    return render(request, 'documento/lista_oficios.html', {
        'oficios': oficios, 'depto': depto, 'year': year,
        'search_query': query, 'fecha_recibido_default': timezone.localdate(),
        'pdf_max_mb': settings.PDF_MAX_MB, 'pdf_max_bytes': settings.PDF_MAX_MB * 1024 * 1024,
    })


def lista_pendientes(request):
    require_admin(request.user)
    try:
        tables = available_tables(allowed_departments(request.user))
        oficios, query = buscar_oficios(request, tables, pendientes=True)
    except DatabaseError:
        logger.exception('Error al consultar oficios pendientes')
        oficios, query = buscar_oficios(request, [])
        messages.error(request, 'No se pudo cargar el listado de pendientes.')
    return render(request, 'documento/lista_pendientes.html', {
        'oficios': oficios, 'depto': 'todos', 'year': 'todos', 'search_query': query,
    })


@require_http_methods(['GET', 'POST'])
def crear_oficio(request, depto, year):
    table = connection.ops.quote_name(require_department(request.user, depto, year))
    if request.method == 'GET':
        return redirect('lista_oficios', depto=depto, year=year)
    form = DocumentCreateForm(request.POST)
    if not form.is_valid():
        messages.error(request, error_message(form))
        return redirect('lista_oficios', depto=depto, year=year)
    data = form.cleaned_data
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"""INSERT INTO {table}
                    (fecha_recibido, fecha_oficio, enviado_por, procedencia, asunto, referencia, pendiente)
                    VALUES (%s,%s,%s,%s,%s,%s,TRUE)""",
                    [data[key] for key in ['fecha_recibido','fecha_oficio','enviado_por','procedencia','asunto','referencia']])
        messages.success(request, 'Oficio creado exitosamente.')
    except DatabaseError:
        logger.exception('No se pudo crear el oficio')
        messages.error(request, 'No se pudo crear el oficio. Intenta nuevamente.')
    return redirect('lista_oficios', depto=depto, year=year)


def grafica(request):
    from .dashboard import dashboard_period, dashboard_statistics

    period = dashboard_period(request.GET.get('mes'), timezone.localdate())
    if period['invalid_month']:
        messages.warning(request, 'El mes indicado no es válido. Se muestra el mes actual.')
    data = []
    try:
        tables = available_tables(allowed_departments(request.user))
        with connection.cursor() as cursor:
            for table in tables:
                cursor.execute(f"""
                    SELECT fecha_recibido, pendiente, departamento, area
                    FROM {connection.ops.quote_name(table)}
                    WHERE activo=TRUE AND fecha_recibido >= %s AND fecha_recibido < %s
                    ORDER BY fecha_recibido DESC
                """, [period['period_start'], period['period_end']])
                columns = [column[0] for column in cursor.description]
                data.extend(dict(zip(columns, row)) for row in cursor.fetchall())
        from apariencia.services import web_branding
        if not hasattr(request, '_ivem_branding'):
            request._ivem_branding = web_branding()
        context = dashboard_statistics(data, period['selected_date'], palette=request._ivem_branding)
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



@require_POST
def asignar_folio(request):
    require_admin(request.user)
    depto, year = parse_table(request.POST.get('tabla_origen'))
    table = connection.ops.quote_name(require_department(request.user, depto, year))
    identifier = record_id(request.POST.get('oficio_id'))
    form = FolioForm(request.POST)
    if not form.is_valid():
        messages.error(request, error_message(form))
        return redirect('lista_pendientes')
    data = form.cleaned_data
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f'SELECT pendiente, folio FROM {table} WHERE id=%s AND activo=TRUE FOR UPDATE', [identifier])
                row = cursor.fetchone()
                if not row:
                    raise Http404('Oficio no encontrado.')
                if not row[0] or row[1] is not None:
                    raise DocumentConflict('El oficio ya tiene folio asignado.')
                # Mantiene la secuencia existente por departamento y año.
                cursor.execute(f"""UPDATE {table} SET pendiente=FALSE,
                    folio=nextval(%s::regclass), asunto_opciones=%s, area=%s, nota=%s
                    WHERE id=%s RETURNING folio""",
                    [f'folio_seq_{depto}_{year}', data['asunto_opciones'], data['area'], data['nota'], identifier])
                folio = cursor.fetchone()[0]
        messages.success(request, f'Folio {folio} asignado correctamente al oficio {identifier}.')
    except DocumentConflict as error:
        messages.error(request, str(error))
    except DatabaseError:
        logger.exception('No se pudo asignar el folio')
        messages.error(request, 'No se pudo asignar el folio. Intenta nuevamente.')
    return redirect('lista_pendientes')


@require_http_methods(['GET'])
def imprimir_oficio(request, depto, year, record_id):
    from .access import record_id as validate_id
    table = connection.ops.quote_name(require_department(request.user, depto, year))
    identifier = validate_id(record_id)
    with connection.cursor() as cursor:
        cursor.execute(f'SELECT * FROM {table} WHERE id=%s AND activo=TRUE AND folio IS NOT NULL', [identifier])
        row = cursor.fetchone()
        if not row:
            raise Http404('Oficio no encontrado o sin folio.')
        data = dict(zip([column[0] for column in cursor.description], row))
    from apariencia.services import print_branding
    return render(request, 'documento/formato_oficio.html', {'data': data, 'depto': depto, 'year': year, 'print_branding': print_branding(year)})


@require_POST
def eliminar_oficio(request, depto, year, id):
    require_admin(request.user)
    table = connection.ops.quote_name(require_department(request.user, depto, year))
    identifier = record_id(id)
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f'UPDATE {table} SET activo=FALSE WHERE id=%s AND activo=TRUE', [identifier])
                if cursor.rowcount != 1:
                    raise Http404('Oficio no encontrado.')
        messages.success(request, 'El oficio fue eliminado correctamente.')
    except DatabaseError:
        logger.exception('No se pudo eliminar el oficio')
        messages.error(request, 'No se pudo eliminar el oficio. Intenta nuevamente.')
    return redirect('lista_oficios', depto=depto, year=year)


@require_http_methods(['GET', 'POST'])
def editar_oficio(request, depto, year, id):
    table = connection.ops.quote_name(require_department(request.user, depto, year))
    identifier = record_id(id)
    if request.method == 'GET':
        return redirect('lista_oficios', depto=depto, year=year)
    form = DocumentEditForm(request.POST)
    if not form.is_valid():
        messages.error(request, error_message(form))
        return redirect('lista_oficios', depto=depto, year=year)
    data = form.cleaned_data
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f'SELECT pendiente, folio FROM {table} WHERE id=%s AND activo=TRUE FOR UPDATE', [identifier])
                row = cursor.fetchone()
                if not row:
                    raise Http404('Oficio no encontrado.')
                if not row[0] or row[1] is not None:
                    raise DocumentConflict('No se puede editar un oficio con folio asignado.')
                cursor.execute(f'UPDATE {table} SET asunto=%s, referencia=%s, enviado_por=%s, procedencia=%s WHERE id=%s',
                               [data['asunto'], data['referencia'], data['enviado_por'], data['procedencia'], identifier])
        messages.success(request, 'El oficio fue actualizado correctamente.')
    except DocumentConflict as error:
        messages.error(request, str(error))
    except DatabaseError:
        logger.exception('No se pudo editar el oficio')
        messages.error(request, 'No se pudo editar el oficio. Intenta nuevamente.')
    return redirect('lista_oficios', depto=depto, year=year)


@require_POST
def archivo(request):
    depto = request.POST.get('depto')
    year = request.POST.get('year')
    try:
        require_department(request.user, depto, year)
        identifier = record_id(request.POST.get('id_oficio'))
    except PermissionDenied:
        return JsonResponse({'success': False, 'message': 'No tienes acceso a este departamento.'}, status=403)
    except Http404:
        return JsonResponse({'success': False, 'message': 'Oficio no válido.'}, status=404)
    action = request.POST.get('action', 'upload')
    if action not in {'upload', 'edit'}:
        return JsonResponse({'success': False, 'message': 'Operación de archivo no válida.'}, status=400)
    try:
        path = saveArchivo(depto, year, identifier, request.FILES.get('archivo'), action=action)
    except ValidationError as error:
        return JsonResponse({'success': False, 'message': ' '.join(error.messages)}, status=400)
    except Http404:
        return JsonResponse({'success': False, 'message': 'Oficio no encontrado.'}, status=404)
    except DocumentConflict as error:
        return JsonResponse({'success': False, 'message': str(error)}, status=409)
    except DatabaseError:
        logger.exception('No se pudo actualizar la referencia del PDF')
        return JsonResponse({'success': False, 'message': 'No se pudo guardar el archivo. El archivo anterior se conserva.'}, status=500)
    except OSError:
        logger.exception('No se pudo guardar el PDF')
        return JsonResponse({'success': False, 'message': 'No se pudo guardar el archivo. Intenta nuevamente.'}, status=500)
    messages.success(request, 'Archivo actualizado exitosamente' if action == 'edit' else 'Archivo cargado exitosamente')
    return JsonResponse({'success': True, 'message': 'Archivo guardado exitosamente', 'file_url': default_storage.url(path)})


def cargar_archivo(request):
    # Compatibilidad para los consumidores internos de la función anterior.
    return archivo(request)


@require_http_methods(['GET', 'HEAD'])
def media_archivo(request, path):
    """Conserva las URL de los PDF antiguos, verificando permisos antes de servirlos."""
    from pathlib import Path
    path = path.replace('\\', '/')
    root = Path(settings.MEDIA_ROOT).resolve()
    try:
        candidate = (root / path).resolve()
    except (OSError, ValueError):
        raise Http404('Archivo no encontrado.')
    if not candidate.is_relative_to(root) or candidate == root:
        raise Http404('Archivo no encontrado.')
    found = False
    for table in available_tables(allowed_departments(request.user)):
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT id FROM {connection.ops.quote_name(table)} WHERE replace(archivo, %s, %s)=%s AND activo=TRUE LIMIT 1", ['\\', '/', path])
            if cursor.fetchone():
                found = True
                break
    if not found:
        raise Http404('Archivo no encontrado.')
    try:
        return FileResponse(candidate.open('rb'), content_type='application/pdf', filename=candidate.name)
    except OSError:
        raise Http404('Archivo no encontrado.')
