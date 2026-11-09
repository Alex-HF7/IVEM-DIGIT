from django.contrib.admin import AdminSite
from operacion.roles import can_enter_admin


class TechnicalAdminSite(AdminSite):
    site_header = 'Administración técnica IVEM'
    site_title = 'Administración técnica'

    def has_permission(self, request):
        return can_enter_admin(request.user)
