from documento.access import can_view_all_documents


def grupo_context(request):
    groups = list(request.user.groups.values_list('name', flat=True)) if request.user.is_authenticated else []
    return {
        'grupos_usuario': groups,
        'can_view_all_documents': can_view_all_documents(request.user),
    }
