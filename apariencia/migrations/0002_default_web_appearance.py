from django.db import migrations


def create_defaults(apps,schema_editor):
    apps.get_model('apariencia','WebAppearance').objects.using(schema_editor.connection.alias).get_or_create(pk=1)


class Migration(migrations.Migration):
    dependencies=[('apariencia','0001_initial')]
    operations=[migrations.RunPython(create_defaults,migrations.RunPython.noop)]
