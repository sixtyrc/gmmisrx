import threading

from django.conf import settings
from django.core.mail import send_mail

from . import openwa


def _resumen(run):
    if run.estado == run.ESTADO_OK:
        titulo = f"Padron actualizado OK - {run.total_enviado_misrx} registros"
    else:
        titulo = "ERROR actualizando el padron"

    cuerpo = (
        f"{titulo}\n\n"
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
    return titulo, cuerpo


def notificar_resultado(run):
    titulo, cuerpo = _resumen(run)
    asunto = f"[MisRx] {titulo}"

    send_mail(
        subject=asunto,
        message=cuerpo,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[settings.NOTIFICACIONES_EMAIL_TO],
        fail_silently=True,
    )

    # Best-effort y en background: si el servidor OpenWA esta caido o tarda, no
    # debe demorar ni romper el pipeline principal (que ya termino su trabajo).
    if settings.NOTIFICACIONES_WHATSAPP_TO:
        hilo = threading.Thread(
            target=openwa.send_text,
            args=(settings.NOTIFICACIONES_WHATSAPP_TO, cuerpo),
            daemon=True,
        )
        hilo.start()
