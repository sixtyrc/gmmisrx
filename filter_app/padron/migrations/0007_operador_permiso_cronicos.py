from django.db import migrations


def agregar_permiso_cronicos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    # Mismo motivo que en 0004_grupos_admin_operador: no depender del signal
    # post_migrate, se crea la Permission explicitamente si hace falta.
    content_type, _ = ContentType.objects.get_or_create(
        app_label="padron", model="cronicolog"
    )
    permiso, _ = Permission.objects.get_or_create(
        codename="can_manage_cronicos",
        content_type=content_type,
        defaults={"name": "Puede cargar/dar de baja prescripciones cronicas en MisRx"},
    )

    operador = Group.objects.filter(name="Operador").first()
    if operador:
        operador.permissions.add(permiso)


def quitar_permiso_cronicos(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    operador = Group.objects.filter(name="Operador").first()
    permiso = Permission.objects.filter(codename="can_manage_cronicos").first()
    if operador and permiso:
        operador.permissions.remove(permiso)


class Migration(migrations.Migration):

    dependencies = [
        ("padron", "0006_vademecumitem"),
    ]

    operations = [
        migrations.RunPython(agregar_permiso_cronicos, quitar_permiso_cronicos),
    ]
