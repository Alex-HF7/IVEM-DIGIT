from django.contrib.admin.apps import AdminConfig


class TechnicalAdminConfig(AdminConfig):
    default_site = 'ivem_digit.admin_site.TechnicalAdminSite'
