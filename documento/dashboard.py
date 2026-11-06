"""Presentación de estadísticas, independiente del idioma del sistema operativo."""
from math import ceil
from datetime import date
import re

import pandas as pd
import plotly.express as px

MONTHS = ('enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
          'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre')
DEPARTMENTS = {'ucg': 'UCG', 'delegacion': 'Delegación'}
COLORS = {'UCG': '#682145', 'Delegación': '#148575'}



def dashboard_period(value, today):
    selected = today.replace(day=1)
    invalid = False
    if value:
        try:
            if not re.fullmatch(r'[0-9]{4}-[0-9]{2}', value):
                raise ValueError
            year, month = map(int, value.split('-'))
            if not 1900 <= year <= 9998:
                raise ValueError
            selected = date(year, month, 1)
        except ValueError:
            invalid = True
    index = selected.year * 12 + selected.month - 1

    def month_at(offset):
        year, month = divmod(index + offset, 12)
        return date(year, month + 1, 1)

    start, end = month_at(-11), month_at(1)
    return {
        'selected_date': selected, 'selected_month': selected.strftime('%Y-%m'),
        'previous_month': month_at(-1).strftime('%Y-%m') if selected > date(1900, 1, 1) else None,
        'next_month': end.strftime('%Y-%m') if selected < date(9998, 12, 1) else None,
        'period_start': start, 'period_end': end,
        'history_label': f'{MONTHS[start.month-1]} {start.year} – {MONTHS[selected.month-1]} {selected.year}',
        'invalid_month': invalid,
    }

def dashboard_statistics(data, today, palette=None):
    palette=palette or {}
    chart_colors={'UCG':palette.get('primary',COLORS['UCG']), 'Delegación':palette.get('accent',COLORS['Delegación'])}
    context = {
        'current_month': f'{MONTHS[today.month - 1]} de {today.year}',
        'total_mes': 0, 'pendientes_mes': 0, 'total_oficios': len(data),
        'pendientes_total': 0, 'no_data': not data,
    }
    if not data:
        return context

    df = pd.DataFrame(data)
    df['fecha_recibido'] = pd.to_datetime(df['fecha_recibido'])
    df['mes'] = df['fecha_recibido'].dt.strftime('%Y-%m')
    df['departamento'] = df['departamento'].replace(DEPARTMENTS)
    area_names = {
        'Dir. General': 'Dirección General', 'direccion': 'Dirección General',
        'Del. Administración': 'Delegación Administrativa', 'delegacion': 'Delegación Administrativa',
        'ucg': 'UCG', 'Sub. Jurídica': 'Subdirección Jurídica', 'juridica': 'Subdirección Jurídica',
        'Sub. planeacion': 'Subdirección de Planeación', 'planeacion': 'Subdirección de Planeación',
        'Sub. Técnica': 'Subdirección Técnica', 'tecnia': 'Subdirección Técnica',
        'Sub. Comercialización': 'Subdirección de Comercialización', 'comercializacion': 'Subdirección de Comercialización',
    }
    areas = df.get('area', pd.Series(index=df.index, dtype='object'))
    df['area'] = areas.fillna('').astype(str).str.strip().replace('', 'Sin área asignada').replace(area_names)
    current = df[(df['fecha_recibido'].dt.month == today.month)
                 & (df['fecha_recibido'].dt.year == today.year)]
    months = sorted(df['mes'].unique())
    labels = {month: f'{MONTHS[int(month[5:]) - 1]} {month[:4]}' for month in months}
    monthly = df.groupby(['mes', 'departamento']).size().reset_index(name='count')
    monthly['mes'] = monthly['mes'].map(labels)
    new = px.bar(monthly, x='mes', y='count', color='departamento',
                 barmode='group', text='count', color_discrete_map=chart_colors,
                 labels={'mes': '', 'count': 'Oficios', 'departamento': ''},
                 category_orders={'mes': [labels[month] for month in months]})
    new.update_xaxes(type='category', tickangle=-25, automargin=True)
    new.update_yaxes(dtick=max(1, ceil(monthly['count'].max() / 5)),
                     tickformat='d', rangemode='tozero', gridcolor='#edf0f4')
    new.update_traces(hovertemplate='%{x}<br>%{y} oficios<extra>%{fullData.name}</extra>')

    pending = current[current['pendiente']].groupby('departamento').size().reset_index(name='count')
    pending_figure = None
    if not pending.empty:
        pending_figure = px.bar(pending, x='count', y='departamento', color='departamento',
                                orientation='h', text='count', color_discrete_map=chart_colors,
                                labels={'count': 'Oficios pendientes', 'departamento': ''})
        pending_figure.update_layout(showlegend=False)
        pending_figure.update_xaxes(dtick=max(1, ceil(pending['count'].max() / 5)),
                                    tickformat='d', rangemode='tozero', gridcolor='#edf0f4')
        pending_figure.update_traces(hovertemplate='%{y}<br>%{x} pendientes<extra></extra>')

    assigned = current.groupby('area').size().reset_index(name='count').sort_values(['count', 'area'])
    assigned_figure = None
    if not assigned.empty:
        assigned_figure = px.bar(assigned, x='count', y='area', orientation='h', text='count',
                                 color_discrete_sequence=[chart_colors['UCG']],
                                 labels={'count': 'Número de oficios', 'area': ''})
        assigned_figure.update_xaxes(dtick=max(1, ceil(assigned['count'].max() / 5)),
                                    tickformat='d', rangemode='tozero', gridcolor='#edf0f4')
        assigned_figure.update_yaxes(type='category', automargin=True)
        assigned_figure.update_traces(hovertemplate='%{y}<br>%{x} oficios<extra></extra>')

    for figure in [new, pending_figure, assigned_figure]:
        if figure is None:
            continue
        figure.update_layout(template='plotly_white', height=380, autosize=True,
                              font={'family': 'Arial, sans-serif', 'color': '#334155', 'size': 13},
                              margin={'l': 30, 'r': 25, 't': 45, 'b': 60},
                              legend={'orientation': 'h', 'y': 1.15, 'x': 0}, bargap=0.35)
        figure.update_traces(textposition='outside', cliponaxis=False)
    if assigned_figure is not None:
        assigned_figure.update_layout(height=max(320, len(assigned) * 48 + 100))
    context.update(total_mes=len(current), pendientes_mes=int(current['pendiente'].sum()),
                   pendientes_total=int(current['pendiente'].sum()),
                   fig_nuevos=new, fig_pendientes=pending_figure, fig_areas=assigned_figure)
    return context
