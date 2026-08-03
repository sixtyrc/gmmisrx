from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .models import AuditLogEntry, PadronRun
from .services.pipeline import ejecutar_actualizacion


def _client_ip(request):
    return request.META.get("REMOTE_ADDR")


@login_required
def dashboard(request):
    corridas = PadronRun.objects.select_related("usuario")[:100]
    puede_ejecutar = request.user.is_superuser or request.user.has_perm("padron.can_run_padron")
    return render(request, "padron/dashboard.html", {
        "corridas": corridas,
        "puede_ejecutar": puede_ejecutar,
    })


@login_required
@permission_required("padron.can_run_padron", raise_exception=True)
@require_POST
def ejecutar_ahora(request):
    AuditLogEntry.objects.create(
        usuario=request.user,
        accion=AuditLogEntry.ACCION_RUN_MANUAL,
        ip_address=_client_ip(request),
        detalle="Disparado desde el panel",
    )
    try:
        run = ejecutar_actualizacion(trigger=PadronRun.TRIGGER_MANUAL, usuario=request.user)
        messages.success(
            request,
            f"Padron actualizado: {run.total_enviado_misrx} registros enviados a MisRx.",
        )
    except Exception as e:
        messages.error(request, f"Error actualizando el padron: {e}")

    return redirect("padron:dashboard")
