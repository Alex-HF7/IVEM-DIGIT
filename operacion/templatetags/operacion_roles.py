from django import template
from operacion.presentation import role_label

register = template.Library()
register.filter('role_label', role_label)
