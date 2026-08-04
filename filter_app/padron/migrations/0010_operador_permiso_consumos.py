from django.db import migrations


def agregar_permiso_consumos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    # Mismo motivo que en 0004_grupos_admin_operador: no depender del signal
    # post_migrate, se crea la Permission explicitamente si hace falta.
    content_type, _ = ContentType.objects.get_or_create(
        app_label="padron", model="consumoconsultalog"
    )
    permiso, _ = Permission.objects.get_or_create(
        codename="can_view_consumos",
        content_type=content_type,
        defaults={"name": "Puede consultar recetas y consumos por DNI en MisRx"},
    )

    operador = Group.objects.filter(name="Operador").first()
    if operador:
        operador.permissions.add(permiso)


def quitar_permiso_consumos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    operador = Group.objects.filter(name="Operador").first()
    permiso = Permission.objects.filter(codename="can_view_consumos").first()
    if operador and permiso:
        operador.permissions.remove(permiso)


class Migration(migrations.Migration):

    dependencies = [
        ("padron", "0009_consumoconsultalog"),
    ]

    operations = [
        migrations.RunPython(agregar_permiso_consumos, quitar_permiso_consumos),
    ]
