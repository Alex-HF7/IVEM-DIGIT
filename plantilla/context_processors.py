from documento.access import can_view_all_documents


def grupo_context(request):
    groups = list(request.user.groups.values_list('name', flat=True)) if request.user.is_authenticated else []
    user = request.user
    has_actions = False
    if user.is_authenticated:
        has_actions = user.is_superuser or any(user.has_perm(code) for code in (
            'auth.add_user', 'auth.view_user',
            'gestion_tables.add_configuraciontable', 'gestion_tables.view_configuraciontable',
            'apariencia.change_webappearance', 'apariencia.change_printidentity', 'apariencia.add_printidentity',
        )) or (user.is_staff and user.has_perm('gestion_tables.access_technical_admin'))
    return {
        'grupos_usuario': groups,
        'has_account_actions': has_actions,
        'can_view_all_documents': can_view_all_documents(request.user),
    }
