from django.db import connection, transaction
from django.shortcuts import redirect, render
from django.contrib import messages
from datetime import datetime, timedelta
from django.utils import timezone
import json
import plotly.express as px
import pandas as pd;

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
                'pendiente': request.POST.get('pendiente', 'false') == 'true'
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
            new_pendiente = request.POST.get('pendiente') == 'true'
            
            with transaction.atomic():
                with connection.cursor() as cursor:
                    if not new_pendiente:  # Si está marcando como NO pendiente
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
                        msg = f"Folio {folio} asignado correctamente"
                    else:
                        cursor.execute(f"""
                            UPDATE oficios_{depto}_{year}
                            SET pendiente = TRUE, folio = NULL
                            WHERE id = %s AND pendiente = FALSE
                        """, [oficio_id])
                        msg = "Marcado como pendiente (folio removido)"
                    
                    messages.success(request, msg)
                    
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
    
    # Consulta para obtener datos de todas las tablas relevantes
    data = []
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
                            asunto_opciones,
                            area,
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
        return render(request, 'dashboard_oficios.html', {'no_data': True})
    
    # Convertir a DataFrame para facilitar el análisis
    df = pd.DataFrame(data)
    
    # Convertir fecha a datetime y extraer año-mes como string
    df['fecha_recibido'] = pd.to_datetime(df['fecha_recibido'])
    df['mes'] = df['fecha_recibido'].dt.strftime('%Y-%m')  # Formato: '2023-01'
    
    # Gráfico 1: Oficios por mes
    oficios_por_mes = df.groupby(['mes', 'departamento']).size().reset_index(name='count')
    
    fig_mes = px.bar(
        oficios_por_mes,
        x='mes',
        y='count',
        color='departamento',
        title='Oficios recibidos por mes',
        labels={'count': 'Número de oficios', 'mes': 'Mes'},
        category_orders={"mes": sorted(df['mes'].unique())}  # Ordenar meses cronológicamente
    )
    
    # Gráfico 2: Distribución por asunto
    asunto_dist = df['asunto_opciones'].value_counts().reset_index()
    fig_asunto = px.pie(
        asunto_dist,
        values='count',
        names='asunto_opciones',
        title='Distribución por tipo de asunto'
    )
    
    # Gráfico 3: Pendientes por área
    pendientes = df[df['pendiente']].groupby(['area', 'departamento']).size().reset_index(name='count')
    fig_pendientes = px.treemap(
        pendientes,
        path=['area', 'departamento'],
        values='count',
        title='Oficios pendientes por área'
    )
    
    # Convertir figuras a HTML
    context = {
        'plot_mes': fig_mes.to_html(full_html=False, include_plotlyjs='cdn'),
        'plot_asunto': fig_asunto.to_html(full_html=False, include_plotlyjs='cdn'),
        'plot_pendientes': fig_pendientes.to_html(full_html=False, include_plotlyjs='cdn'),
        'total_oficios': len(df),
        'pendientes_total': len(df[df['pendiente']]),
        'no_data': False
    }
    return render(request, 'documento/grafica.html', context)