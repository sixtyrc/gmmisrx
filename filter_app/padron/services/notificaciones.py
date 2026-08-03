from django.conf import settings
from django.core.mail import send_mail


def notificar_resultado(run):
    if run.estado == run.ESTADO_OK:
        asunto = f"[MisRx] Padron actualizado OK - {run.total_enviado_misrx} registros"
    else:
        asunto = "[MisRx] ERROR actualizando el padron"

    cuerpo = (
        f"Corrida #{run.pk} ({run.disparado_por})\n"
        f"Estado: {run.estado}\n"
        f"Total consultado en GX: {run.total_consulta_gx}\n"
        f"Total enviado a MisRx: {run.total_enviado_misrx}\n"
        f"Altas respecto a la corrida anterior: {run.altas_count}\n"
        f"Bajas respecto a la corrida anterior: {run.bajas_count}\n"
        f"Archivo: {run.archivo_generado}\n"
        f"Estado MisRx: {run.misrx_estado_descripcion}\n"
    )
    if run.error_mensaje:
        cuerpo += f"\nError:\n{run.error_mensaje}\n"

    send_mail(
        subject=asunto,
        message=cuerpo,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[settings.NOTIFICACIONES_EMAIL_TO],
        fail_silently=True,
    )
