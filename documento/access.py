"""Validación compartida para las tablas anuales y los permisos de acceso."""
import re
from django.core.exceptions import PermissionDenied
from django.http import Http404

GROUPS = {'ucg': 'UCG', 'delegacion': 'Delegacion'}


def table_name(depto, year):
    if depto not in GROUPS or not re.fullmatch(r'[0-9]{4}', str(year)) or not 1 <= int(year) <= 9999:
        raise Http404('Departamento o año no válido.')
    return f'oficios_{depto}_{int(year):04d}'


def parse_table(name):
    match = re.fullmatch(r'oficios_(ucg|delegacion)_([0-9]{4})', name or '')
    if not match:
        raise Http404('Tabla de oficios no válida.')
    depto, year = match.groups()
    table_name(depto, year)
    return depto, int(year)


def record_id(value):
    if not re.fullmatch(r'[0-9]{1,10}', str(value or '')) or not 1 <= int(value) <= 2147483647:
        raise Http404('Oficio no válido.')
    return int(value)


def has_document_permission(user, code):
    return (user.is_authenticated and getattr(user, 'is_active', True) and
            (user.is_superuser or user.has_perm('gestion_tables.' + code)))


def require_document_permission(user, code):
    if not has_document_permission(user, code):
        raise PermissionDenied('No tienes permiso para esta operación de oficios.')


def can_view_all_documents(user):
    return has_document_permission(user, 'view_all_documents')


def allowed_departments(user):
    if can_view_all_documents(user):
        return set(GROUPS)
    if not user.is_authenticated or not getattr(user, 'is_active', True):
        return set()
    groups = set(user.groups.values_list('name', flat=True))
    return {depto for depto, group in GROUPS.items() if group in groups}


def require_department(user, depto, year):
    name = table_name(depto, year)
    if depto not in allowed_departments(user):
        raise PermissionDenied('No tienes acceso a este departamento.')
    return name


def available_tables(departments):
    from django.db import connection
    if not departments:
        return []
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema='public' AND table_name ~ '^oficios_(ucg|delegacion)_[0-9]{4}$'
            ORDER BY table_name
        """)
        return [row[0] for row in cursor.fetchall() if parse_table(row[0])[0] in departments]
