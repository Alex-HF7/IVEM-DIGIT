from django.db.models.signals import post_save, post_migrate
from django.dispatch import receiver
from .models import ConfiguracionTable
from .services import create_yearly_tables


@receiver(post_migrate, dispatch_uid='gestion_tables.setup_years')
def setup_dynamic_models(sender, using='default', **kwargs):
    if sender.name == 'gestion_tables':
        for year in ConfiguracionTable.objects.using(using).values_list('anno', flat=True):
            create_yearly_tables(year, using=using)


@receiver(post_save, sender=ConfiguracionTable, dispatch_uid='gestion_tables.ensure_year')
def handle_config_save(sender, instance, using='default', raw=False, **kwargs):
    if not raw:
        create_yearly_tables(instance.anno, using=using)


def verify_tables(using='default'):
    for year in ConfiguracionTable.objects.using(using).values_list('anno', flat=True):
        create_yearly_tables(year, using=using)
