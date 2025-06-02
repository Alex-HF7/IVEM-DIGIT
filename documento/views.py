import os
import logging
from django.conf import settings
from django.db import connection, transaction
from django.shortcuts import redirect, render
from django.contrib import messages
from datetime import datetime, timedelta
from django.utils import timezone
from django.http import JsonResponse
import plotly.express as px
import pandas as pd;
from django.http import Http404
from .utils import getRegistros, saveArchivo, paginar

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
    tabla_nombre = f'oficios_{depto}_{year}'
    try:
        oficios_raw = getRegistros(
            tabla_nombre,
            filtros={'activo': True},
            order_by='id DESC'
        )
        # Convertir los valores booleanos correctamente
        for oficio in oficios_raw:
            if 'pendiente' in oficio:
                oficio['pendiente'] = bool(oficio['pendiente'])
            oficio['pendiente_value'] = str(not oficio.get('pendiente', False)).lower()
    except Exception as e:
        oficios_raw = []
        messages.error(request, f"Error al obtener oficios: {str(e)}")
    
    # Filtro búsqueda
    query = request.GET.get('q', '').strip().lower()
    if query:
        oficios_raw = [
            o for o in oficios_raw
            if any(query in str(o.get(field, '')).lower() for field in [
                'folio', 'asunto', 'procedencia', 'referencia', 'depto_asignado', 'enviado_por'
            ])
        ]
    oficios = paginar(request, oficios_raw)
    return render(request, 'documento/lista_oficios.html', {
        'oficios': oficios,
        'depto': depto,
        'year': year,
        'search_query': query
    })

def lista_pendientes(request):
    oficios_pendientes_raw= []
    try:
        with connection.cursor() as cursor:
            # Obtener todas las tablas de oficios
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables
                WHERE table_name LIKE 'oficios\\_%\\_%'
                AND table_schema = 'public'
            """)
            
            tablas = [row[0] for row in cursor.fetchall()]

            for tabla in tablas:
                try:
                    # Verificar si la tabla tiene la columna 'pendiente'
                    cursor.execute(f"""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_name = %s AND column_name = 'pendiente'
                    """, [tabla])
                    if cursor.fetchone():
                        # Obtener los registros pendientes
                        cursor.execute(f"""
                            SELECT *, '{tabla}' AS tabla_origen
                            FROM {tabla}
                            WHERE pendiente = TRUE AND activo = TRUE
                            ORDER BY id ASC
                        """)
                        columns = [col[0] for col in cursor.description]
                        resultados = [dict(zip(columns, row)) for row in cursor.fetchall()]

                        for oficio in resultados:
                            oficio['pendiente_value'] = 'false'  # ya está pendiente, false para el checkbox
                        oficios_pendientes_raw.extend(resultados)

                except Exception as e:
                    messages.warning(request, f"Error consultando {tabla}: {str(e)}")
    except Exception as e:
        messages.error(request, f"Error al obtener tablas de oficios: {str(e)}")
    
    oficios_pendientes = paginar(request, oficios_pendientes_raw)
    return render(request, 'documento/lista_pendientes.html', {
        'oficios': oficios_pendientes,
        'depto': 'todos',
        'year': 'todos'
    })

def crear_oficio(request, depto, year):
    if request.method == 'POST':
        try:
            required_fields = ['fecha_recibido', 'enviado_por', 'procedencia', 'asunto']
            if not all(request.POST.get(field) for field in required_fields):
                raise ValueError("Faltan campos obligatorios")
            data = {
                'fecha_recibido': datetime.strptime(request.POST['fecha_recibido'], '%Y-%m-%d').date(),
                'fecha_oficio': datetime.strptime(request.POST['fecha_oficio'], '%Y-%m-%d').date() if request.POST.get('fecha_oficio') else None,
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
    # Obtener el año actual y los últimos 3 años
    current_year = timezone.now().year
    years = [current_year - i for i in range(3)]
    
    data = []
    
    try:
        # Consulta para obtener datos de todas las tablas relevantes
        for year in years:
            for depto in ['ucg', 'delegacion']:
                table_name = f'oficios_{depto}_{year}'
                
                # Verificar si la tabla existe
                with connection.cursor() as cursor:
                    cursor.execute(f"""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = '{table_name}'
                        );
                    """)
                    table_exists = cursor.fetchone()[0]
                    
                    if table_exists:
                        # Consultar datos de la tabla
                        cursor.execute(f"""
                            SELECT 
                                fecha_recibido,
                                pendiente,
                                departamento
                            FROM {table_name}
                            WHERE fecha_recibido >= %s
                            ORDER BY fecha_recibido DESC
                        """, [timezone.now() - timedelta(days=365)])
                        
                        columns = [col[0] for col in cursor.description]
                        rows = cursor.fetchall()
                        
                        for row in rows:
                            data.append(dict(zip(columns, row)))
        
        if not data:
            return render(request, 'documento/grafica.html', {'no_data': True})
        
        # Convertir a DataFrame para facilitar el análisis
        df = pd.DataFrame(data)
        
        # Convertir fecha a datetime y extraer año-mes
        df['fecha_recibido'] = pd.to_datetime(df['fecha_recibido'])
        df['mes'] = df['fecha_recibido'].dt.strftime('%Y-%m')
        
        # Gráfico 1: Oficios por mes (nuevos registros)
        oficios_por_mes = df.groupby(['mes', 'departamento']).size().reset_index(name='count')
        
        fig_nuevos = px.bar(
            oficios_por_mes,
            x='mes',
            y='count',
            color='departamento',
            title='Nuevos oficios recibidos por mes',
            labels={'count': 'Número de oficios', 'mes': 'Mes'},
            category_orders={"mes": sorted(df['mes'].unique())}
        )
        
        # Gráfico 2: Oficios pendientes
        pendientes = df[df['pendiente']].groupby('departamento').size().reset_index(name='count')
        
        if not pendientes.empty:
            fig_pendientes = px.bar(
                pendientes,
                x='departamento',
                y='count',
                title='Oficios pendientes por departamento',
                labels={'count': 'Número de oficios', 'departamento': 'Departamento'}
            )
            plot_pendientes = fig_pendientes.to_html(full_html=False, include_plotlyjs='cdn')
        else:
            plot_pendientes = None
        
        context = {
            'plot_nuevos': fig_nuevos.to_html(full_html=False, include_plotlyjs='cdn'),
            'plot_pendientes': plot_pendientes,
            'total_oficios': len(df),
            'pendientes_total': len(df[df['pendiente']]),
            'no_data': False
        }
        
    except Exception as e:
        # En caso de cualquier error, mostrar mensaje de no datos
        print(f"Error al generar gráficas: {e}")
        return render(request, 'documento/grafica.html', {'no_data': True})
    
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

            if not all([tabla_origen, oficio_id, asunto_opciones, area, nota]):
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
            return JsonResponse({
                'success': True,
                'message': 'Archivo guardado exitosamente',
                'file_url': os.path.join(settings.MEDIA_URL, ruta_relativa)
            })

        except Exception as e:
            logger.error(f"Error al procesar archivo: {str(e)}", exc_info=True)
            return JsonResponse({'success': False, 'message': f'Error al procesar archivo: {str(e)}'}, status=500)
    return JsonResponse({'success': False, 'message': 'Método no permitido'}, status=405)