from django.db import connection
from django.shortcuts import redirect, render
from django.contrib import messages
from datetime import datetime

# Create your views here.
def list(request):
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
    oficios = []

    with connection.cursor() as cursor:
        cursor.execute(f"SELECT * FROM {tabla_nombre}")
        columns = [col[0] for col in cursor.description]
        for row in cursor.fetchall():
            oficios.append(dict(zip(columns, row)))
    return render(request, 'documento/lista_oficios.html',{
        'oficios': oficios,
        'year': year,
        'depto': depto
    })

def crear_oficio(request, depto, year):
    if request.method == 'POST':
        # Obtener datos del formulario
        fecha_recibido = request.POST.get('fecha_recibido')
        fecha_oficio = request.POST.get('fecha_oficio') or None
        enviado_por = request.POST.get('enviado_por')
        procedencia = request.POST.get('procedencia')
        asunto = request.POST.get('asunto')
        referencia = request.POST.get('referencia')
        
        # Validar campos obligatorios
        if not all([fecha_recibido, enviado_por, procedencia, asunto]):
            messages.error(request, "Faltan campos obligatorios")
            return redirect('lista_oficios', depto=depto, year=year)
        
        try:
            # Formatear fechas
            fecha_recibido = datetime.strptime(fecha_recibido, '%Y-%m-%d').date()
            if fecha_oficio:
                fecha_oficio = datetime.strptime(fecha_oficio, '%Y-%m-%d').date()
            
            # Nombre de la tabla
            tabla_nombre = f'oficios_{depto}_{year}'
            
            # Consulta SQL para insertar
            with connection.cursor() as cursor:
                # Si hay archivo, guardar la ruta
                
                cursor.execute(f"""
                    INSERT INTO {tabla_nombre} (
                        fecha_recibido, fecha_oficio, 
                        enviado_por, procedencia, asunto, 
                        referencia, departamento
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s,
                    )
                """, [
                    fecha_recibido, fecha_oficio,
                    enviado_por, procedencia, asunto,
                    referencia, depto
                ])
                
            
            messages.success(request, "Oficio creado exitosamente")
            return redirect('lista_oficios', depto=depto, year=year)
            
        except Exception as e:
            messages.error(request, f"Error al crear oficio: {str(e)}")
            return redirect('lista_oficios', depto=depto, year=year)
    
    # Si no es POST, mostrar el formulario
    return render(request, 'tu_template.html', {
        'depto': depto,
        'year': year
    })