import os

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Crea el usuario admin inicial (superuser, desde ADMIN_USERNAME/ADMIN_PASSWORD "
        "en .env) y el usuario de servicio 'automatizacion' (sin password, solo para "
        "atribuir las corridas automaticas en la auditoria). Idempotente."
    )

    def handle(self, *args, **options):
        User = get_user_model()

        admin_username = os.environ.get("ADMIN_USERNAME")
        admin_password = os.environ.get("ADMIN_PASSWORD")

        if not User.objects.filter(username=admin_username).exists():
            if not admin_username or not admin_password:
                raise CommandError(
                    "Faltan ADMIN_USERNAME/ADMIN_PASSWORD en .env para crear el admin."
                )
            admin = User.objects.create_superuser(
                username=admin_username, email="", password=admin_password
            )
            admin.groups.add(Group.objects.get(name="Admin"))
            self.stdout.write(self.style.SUCCESS(f"Usuario admin '{admin_username}' creado."))
        else:
            self.stdout.write(f"Usuario admin '{admin_username}' ya existia, no se toca.")

        if not User.objects.filter(username="automatizacion").exists():
            auto = User.objects.create_user(username="automatizacion", email="")
            auto.set_unusable_password()
            auto.is_active = True
            auto.save()
            self.stdout.write(self.style.SUCCESS("Usuario 'automatizacion' creado (sin password, no puede loguearse)."))
        else:
            self.stdout.write("Usuario 'automatizacion' ya existia, no se toca.")
