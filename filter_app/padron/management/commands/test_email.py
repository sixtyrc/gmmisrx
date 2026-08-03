from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Envia un mail de prueba via SMTP (Resend) para validar la configuracion."

    def handle(self, *args, **options):
        destinatario = settings.NOTIFICACIONES_EMAIL_TO
        enviados = send_mail(
            subject="Prueba - Automatizacion padron MisRx",
            message="Prueba de envio desde el proyecto de automatizacion del padron MisRx.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[destinatario],
        )
        self.stdout.write(self.style.SUCCESS(f"Enviados: {enviados} a {destinatario}"))
