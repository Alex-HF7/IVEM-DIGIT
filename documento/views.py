from django.db import connection
from django.shortcuts import render

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