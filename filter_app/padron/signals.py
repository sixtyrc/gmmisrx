from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from .models import AuditLogEntry


def _client_ip(request):
    if request is None:
        return None
    return request.META.get("REMOTE_ADDR")


@receiver(user_logged_in)
def registrar_login_ok(sender, request, user, **kwargs):
    AuditLogEntry.objects.create(
        usuario=user,
        username_intentado=user.username,
        accion=AuditLogEntry.ACCION_LOGIN_OK,
        ip_address=_client_ip(request),
    )


@receiver(user_login_failed)
def registrar_login_fallido(sender, credentials, request=None, **kwargs):
    AuditLogEntry.objects.create(
        username_intentado=credentials.get("username", ""),
        accion=AuditLogEntry.ACCION_LOGIN_FAIL,
        ip_address=_client_ip(request),
    )
