from django.db import connection, transaction
from django.shortcuts import redirect, render
from django.contrib import messages
from datetime import datetime, timedelta
from django.utils import timezone
from ivem_digit import settings
import plotly.express as px
import pandas as pd;
import os
from django.core.files.storage import FileSystemStorage

# Create your views here.
def list(request):
    print("Configuración actual de DB:", connection.settings_dict)
    return render(request, 'documento/listDoc.html')

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
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT * FROM {tabla_nombre}")
            columns = [col[0] for col in cursor.description]
            oficios = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            # Convertir los valores booleanos correctamente
            for oficio in oficios:
                if 'pendiente' in oficio:
                    oficio['pendiente'] = bool(oficio['pendiente'])
                
                # Agregar el valor para el template
                oficio['pendiente_value'] = str(not oficio.get('pendiente', False)).lower()
    except Exception as e:
        oficios = []
        messages.error(request, f"Error al obtener oficios: {str(e)}")
    
    return render(request, 'documento/lista_oficios.html', {
        'oficios': oficios,
        'depto': depto,
        'year': year
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

def actualizar_pendiente(request, depto, year, oficio_id):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(f"""
                        UPDATE oficios_{depto}_{year}
                        SET pendiente = FALSE, 
                            folio = nextval('folio_seq_{depto}_{year}')
                        WHERE id = %s AND pendiente = TRUE
                        RETURNING folio;
                        """, [oficio_id])
                        
                    if cursor.rowcount == 0:
                        raise ValueError("No se pudo actualizar - ¿Ya tenía folio?")
                            
                    folio = cursor.fetchone()[0]
                    messages.success(request, f"Folio {folio} asignado correctamente")
                    
        except Exception as e:
            messages.error(request, f"Error al actualizar: {str(e)}")
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error actualizar oficio {oficio_id}: {str(e)}", exc_info=True)
    
    return redirect('lista_oficios', depto=depto, year=year)

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

def cargar_archivo(request, depto, year, oficio_id):
    print("\nDEBUG: Inicio de la función cargar_archivo")  # Debug 1
    
    if request.method == 'POST':
        try:
            print("DEBUG: Método POST detectado")  # Debug 2
            
            # Verificación de archivo
            if 'archivo_pdf' not in request.FILES:
                raise ValueError("Debes seleccionar un archivo PDF")
            
            pdf_file = request.FILES['archivo_pdf']
            print(f"DEBUG: Archivo recibido - Nombre: {pdf_file.name}, Tamaño: {pdf_file.size}")  # Debug 3

            # Generación de rutas
            nombre_tabla = f"oficios_{depto}_{year}"
            upload_dir = os.path.join(settings.MEDIA_ROOT, 'oficios', depto, str(year))
            os.makedirs(upload_dir, exist_ok=True)
            
            filename = f"oficio_{oficio_id}_{pdf_file.name}"
            filepath = os.path.join(upload_dir, filename)
            relative_path = os.path.join('oficios', depto, str(year), filename).replace('\\', '/')
            
            print(f"DEBUG: Ruta física: {filepath}")  # Debug 4
            print(f"DEBUG: Ruta para DB: {relative_path}")  # Debug 5

            # Guardado físico
            with open(filepath, 'wb+') as destination:
                for chunk in pdf_file.chunks():
                    destination.write(chunk)
            print("DEBUG: Archivo guardado físicamente")  # Debug 6

            # Actualización en BD
            with connection.cursor() as cursor:
                query = f"UPDATE {nombre_tabla} SET archivo = %s WHERE id = %s"
                params = [relative_path, oficio_id]
                print(f"DEBUG: Query: {query % tuple(params)}")  # Debug 7
                
                cursor.execute(query, params)
                print(f"DEBUG: Filas afectadas: {cursor.rowcount}")  # Debug 8
                
                # Verificación adicional para PostgreSQL
                if hasattr(connection, 'commit'):
                    connection.commit()
                    print("DEBUG: Commit ejecutado")  # Debug 9
            
            messages.success(request, "¡Archivo guardado correctamente!")
            return redirect('lista_oficios', depto=depto, year=year)
            
        except Exception as e:
            print(f"DEBUG: Error - {str(e)}")  # Debug 10
            messages.error(request, f"Error al guardar: {str(e)}")
            return redirect('lista_oficios', depto=depto, year=year)
    
    return redirect('lista_oficios', depto=depto, year=year)