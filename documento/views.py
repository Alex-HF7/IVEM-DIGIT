from django.db import connection, transaction
from django.shortcuts import redirect, render
from django.contrib import messages
from datetime import datetime

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
                if not data['pendiente']:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT nextval('folio_sequence')")
                        data['folio'] = cursor.fetchone()[0]
            
                columns = [k for k in data.keys() if data[k] is not None]
                values = [data[k] for k in columns]
                placeholders = ', '.join(['%s'] * len(values))

                with connection.cursor() as cursor:
                    cursor.execute(
                        f"INSERT INTO oficios_{depto}_{year} ({', '.join(columns)}) VALUES ({placeholders})",
                        values
                    )
            messages.success(request, "Oficio creado exitosamente!")
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
            tabla_nombre = f'oficios_{depto}_{year}'
            
            with connection.cursor() as cursor:
                # Verificar si está marcando como no pendiente
                if request.POST.get('pendiente') == 'false':
                    cursor.execute("SELECT nextval('folio_sequence')")
                    folio = cursor.fetchone()[0]
                    
                    cursor.execute(f"""
                        UPDATE {tabla_nombre} 
                        SET folio = %s, pendiente = false
                        WHERE id = %s
                    """, [folio, oficio_id])
                else:
                    cursor.execute(f"""
                        UPDATE {tabla_nombre}
                        SET folio = NULL, pendiente = true
                        WHERE id = %s
                    """, [oficio_id])
                
                messages.success(request, "Estado actualizado correctamente")
        except Exception as e:
            messages.error(request, f"Error al actualizar: {str(e)}")
    
    return redirect('lista_oficios', depto=depto, year=year)