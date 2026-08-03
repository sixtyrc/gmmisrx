from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_POST

from .models import AuditLogEntry, PadronRun
from .services.pipeline import ejecutar_actualizacion

CORRIDAS_POR_PAGINA = 15

# Buscador de DNI: implementado y funcional, oculto en el panel a pedido del usuario
# (queda como referencia contra la ultima corrida exitosa si se necesita reactivar).
MOSTRAR_BUSCADOR_DNI = False


def _client_ip(request):
    return request.META.get("REMOTE_ADDR")


@login_required
def dashboard(request):
    corridas_qs = PadronRun.objects.select_related("usuario")

    fecha_filtro = request.GET.get("fecha", "").strip()
    fecha_valida = parse_date(fecha_filtro) if fecha_filtro else None
    if fecha_valida:
        corridas_qs = corridas_qs.filter(iniciado_en__date=fecha_valida)

    paginator = Paginator(corridas_qs, CORRIDAS_POR_PAGINA)
    corridas = paginator.get_page(request.GET.get("page"))

    puede_ejecutar = request.user.is_superuser or request.user.has_perm("padron.can_run_padron")
    ultima_ok = PadronRun.objects.filter(estado=PadronRun.ESTADO_OK).order_by("-iniciado_en").first()

    resultado_dni = None
    if MOSTRAR_BUSCADOR_DNI:
        dni_buscado = "".join(ch for ch in request.GET.get("dni", "") if ch.isdigit())
        if dni_buscado:
            if ultima_ok is not None:
                resultado_dni = {
                    "dni": dni_buscado,
                    "activo": dni_buscado in ultima_ok.dnis_incluidos,
                    "fecha_referencia": ultima_ok.iniciado_en,
                }
            else:
                resultado_dni = {"dni": dni_buscado, "activo": None, "fecha_referencia": None}

    return render(request, "padron/dashboard.html", {
        "corridas": corridas,
        "puede_ejecutar": puede_ejecutar,
        "ultima_ok": ultima_ok,
        "resultado_dni": resultado_dni,
        "mostrar_buscador_dni": MOSTRAR_BUSCADOR_DNI,
        "fecha_filtro": fecha_filtro,
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
