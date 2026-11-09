import logging
from django.contrib import messages
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction, DatabaseError
from django.db.models import Q
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from gestion_tables.models import ConfiguracionTable
from .forms import OperatorUserForm, AnnualFolderForm

logger = logging.getLogger(__name__)


def audit_creation(actor, obj, message):
    LogEntry.objects.log_actions(user_id=actor.pk, queryset=type(obj).objects.filter(pk=obj.pk),
                                 action_flag=ADDITION, change_message=message)


@login_required
@require_http_methods(['GET', 'POST'])
def users(request):
    can_add = request.user.has_perm('auth.add_user')
    can_view = request.user.has_perm('auth.view_user')
    if not (can_add or can_view) or (request.method == 'POST' and not can_add):
        raise PermissionDenied
    form = OperatorUserForm(request.POST if request.method == 'POST' else None, actor=request.user) if can_add else None
    if form and request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                user = form.save()
                audit_creation(request.user, user, 'Cuenta creada desde la gestión de usuarios de la aplicación.')
        except DatabaseError:
            logger.exception('No se pudo crear la cuenta')
            form.add_error(None, 'No se pudo crear la cuenta. Comprueba si el usuario ya existe e intenta de nuevo.')
        else:
            messages.success(request, 'Usuario creado correctamente. Ya puede iniciar sesión con sus credenciales.')
            return redirect('operacion:users')
    query = request.GET.get('q', '').strip()[:150]
    accounts = get_user_model().objects.none()
    if can_view:
        accounts = get_user_model().objects.order_by('username').prefetch_related('groups')
        if query:
            accounts = accounts.filter(Q(username__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query))
    page = Paginator(accounts, 20).get_page(request.GET.get('page'))
    return render(request, 'operacion/users.html', {'form': form, 'accounts': page, 'can_view': can_view, 'query': query})


@login_required
@require_http_methods(['GET', 'POST'])
def folders(request):
    can_add = request.user.has_perm('gestion_tables.add_configuraciontable')
    can_view = request.user.has_perm('gestion_tables.view_configuraciontable')
    if not (can_add or can_view) or (request.method == 'POST' and not can_add):
        raise PermissionDenied
    current = timezone.localdate().year
    proposed = current + 1 if ConfiguracionTable.objects.filter(anno=current).exists() else current
    form = AnnualFolderForm(request.POST if request.method == 'POST' else None, initial={'anno': proposed}) if can_add else None
    if form and request.method == 'POST' and form.is_valid():
        try:
            with transaction.atomic():
                folder = form.save()
                audit_creation(request.user, folder, 'Carpetas anuales creadas automáticamente desde la aplicación.')
        except DatabaseError:
            logger.exception('No se pudieron crear las carpetas anuales')
            form.add_error(None, 'No se pudieron crear las carpetas. No se guardaron cambios; intenta de nuevo o contacta al responsable técnico.')
        else:
            messages.success(request, f'Carpetas de {folder.anno} disponibles para UCG y Delegación.')
            return redirect('operacion:folders')
    records = ConfiguracionTable.objects.order_by('-anno') if can_view else ConfiguracionTable.objects.none()
    page = Paginator(records, 20).get_page(request.GET.get('page'))
    return render(request, 'operacion/folders.html', {'form': form, 'folders': page, 'can_view': can_view})
