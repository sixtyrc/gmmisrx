from django.db import migrations


def crear_grupos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    # No depender del signal post_migrate (todavia no corrio en este mismo
    # comando migrate): se crea la Permission explicitamente si hace falta.
    content_type, _ = ContentType.objects.get_or_create(
        app_label="padron", model="padronrun"
    )
    permiso_ejecutar, _ = Permission.objects.get_or_create(
        codename="can_run_padron",
        content_type=content_type,
        defaults={"name": "Puede ejecutar la actualizacion del padron manualmente"},
    )

    operador, _ = Group.objects.get_or_create(name="Operador")
    operador.permissions.set([permiso_ejecutar])

    # Admin usa is_superuser (acceso total, incluido /admin), el grupo queda
    # como referencia/organizacion pero no necesita permisos explicitos.
    Group.objects.get_or_create(name="Admin")


def eliminar_grupos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=["Admin", "Operador"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("padron", "0003_alter_padronrun_options"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(crear_grupos, eliminar_grupos),
    ]
