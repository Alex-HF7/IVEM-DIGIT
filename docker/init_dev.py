"""Prepara grupos y tablas del año actual; no crea cuentas ni contraseñas."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ivem_digit.settings_local')

import django

django.setup()

from django.contrib.auth.models import Group
from django.utils import timezone
from gestion_tables.models import ConfiguracionTable

for name in ['UCG', 'Delegacion']:
    Group.objects.get_or_create(name=name)
ConfiguracionTable.objects.get_or_create(
    anno=timezone.localdate().year,
    defaults={'descripcion': 'Desarrollo local'},
)
