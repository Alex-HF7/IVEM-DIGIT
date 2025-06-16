def grupo_context(request):
    if request.user.is_authenticated:
        grupos_usuario = list(request.user.groups.values_list('name', flat=True))
        es_staff = request.user.is_staff
    else:
        grupos_usuario = []
        es_staff = False
    return {
        'grupos_usuario': grupos_usuario,
        'es_staff': es_staff,
    }