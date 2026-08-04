import json
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_POST

from .models import AuditLogEntry, ConsumoConsultaLog, CronicoLog, PadronRun
from .services import gx_query, misrx_client, planes, vademecum
from .services.pipeline import ejecutar_actualizacion

CORRIDAS_POR_PAGINA = 15

# Buscador de DNI: implementado y funcional, oculto en el panel a pedido del usuario
# (queda como referencia contra la ultima corrida exitosa si se necesita reactivar).
MOSTRAR_BUSCADOR_DNI = False


def _client_ip(request):
    return request.META.get("REMOTE_ADDR")


# Horario fijo de la tarea programada (Windows Task Scheduler, ver docs/DEPLOY.md)
# - no hay forma de leerlo en vivo desde Django, es solo informativo en el panel.
HORA_CORRIDA_AUTOMATICA = (15, 30)


def _proxima_corrida_automatica():
    ahora = timezone.localtime()
    hora, minuto = HORA_CORRIDA_AUTOMATICA
    proxima = ahora.replace(hour=hora, minute=minuto, second=0, microsecond=0)
    if proxima <= ahora:
        proxima += timedelta(days=1)
    return proxima


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
        "proxima_corrida_automatica_iso": _proxima_corrida_automatica().isoformat(),
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


def _puede_gestionar_cronicos(user):
    return user.is_superuser or user.has_perm("padron.can_manage_cronicos")


@login_required
def cronicos(request):
    if not _puede_gestionar_cronicos(request.user):
        return render(request, "403.html", status=403)

    dni_buscado = "".join(ch for ch in request.GET.get("dni", "") if ch.isdigit())
    afiliado_gx = None
    cronicos_misrx = None
    error_consulta = None

    if dni_buscado:
        afiliado_gx = gx_query.buscar_afiliado_por_dni(dni_buscado)
        if afiliado_gx is not None:
            try:
                cronicos_misrx = misrx_client.consultar_cronicos(afiliado_gx["nro_afiliado"])
            except Exception as e:
                error_consulta = str(e)

    # El detalle de la bitacora (quien hizo que) es solo para admin; un operador
    # puede operar pero no ver el historial completo de todos.
    ultimos_logs = []
    ultimas_actualizaciones_vademecum = []
    if request.user.is_superuser:
        ultimos_logs = CronicoLog.objects.select_related("usuario")[:20]
        ultimas_actualizaciones_vademecum = AuditLogEntry.objects.filter(
            accion=AuditLogEntry.ACCION_VADEMECUM_ACTUALIZADO
        ).select_related("usuario")[:5]

    return render(request, "padron/cronicos.html", {
        "dni_buscado": dni_buscado,
        "afiliado_gx": afiliado_gx,
        "cronicos_misrx": cronicos_misrx,
        "error_consulta": error_consulta,
        "ultimos_logs": ultimos_logs,
        "ultimas_actualizaciones_vademecum": ultimas_actualizaciones_vademecum,
        "vademecum_stats": vademecum.estadisticas(),
    })


def _puede_ver_consumos(user):
    return user.is_superuser or user.has_perm("padron.can_view_consumos")


@login_required
def consumos(request):
    """Consulta de recetas/consumo por DNI (solo lectura, motor de consultas
    predefinidas de MisRx). A diferencia de cronicos, no hay ninguna accion de
    escritura aca - por eso el permiso para consultar y para ver la bitacora
    de quien consulto que es el mismo, abierto a Operador (ver
    feedback-rollback-features-sensibles: el split "puede operar" vs "puede
    ver todo" es para acciones que escriben/son dificiles de deshacer, no
    aplica a una pantalla que solo lee)."""
    if not _puede_ver_consumos(request.user):
        return render(request, "403.html", status=403)

    dni_buscado = "".join(ch for ch in request.GET.get("dni", "") if ch.isdigit())
    afiliado_gx = None
    items = None
    total_reg = None
    error_consulta = None

    if dni_buscado:
        afiliado_gx = gx_query.buscar_afiliado_por_dni(dni_buscado)
        try:
            respuesta = misrx_client.consultar_consumo(dni_buscado)
            total_reg = respuesta.get("total_reg", 0)
            items = [misrx_client.normalizar_item_consumo(f) for f in (respuesta.get("data") or [])]
            for it in items:
                it["fecha_validacion"] = parse_datetime(it["fecha_validacion"]) if it["fecha_validacion"] else None
                it["fecha_prescripcion"] = parse_datetime(it["fecha_prescripcion"]) if it["fecha_prescripcion"] else None
                it["plan_nombre"] = planes.nombre_plan(it["plan"])
            items.sort(key=lambda it: it["fecha_validacion"] or datetime.min, reverse=True)
        except Exception as e:
            error_consulta = str(e)

        ConsumoConsultaLog.objects.create(
            usuario=request.user,
            dni=dni_buscado,
            total_recetas=total_reg,
            exitoso=error_consulta is None,
            error=error_consulta or "",
        )

    ultimas_consultas = ConsumoConsultaLog.objects.select_related("usuario")[:20]

    return render(request, "padron/consumos.html", {
        "dni_buscado": dni_buscado,
        "afiliado_gx": afiliado_gx,
        "items": items,
        "total_reg": total_reg,
        "error_consulta": error_consulta,
        "ultimas_consultas": ultimas_consultas,
    })


_PERIODO_TIPO_TEXTO_A_CODIGO = {
    "dia": 0, "dias": 0, "diario": 0,
    "mensual": 1, "mes": 1,
    "anual": 2, "año": 2, "ano": 2,
}


def _periodo_tipo_codigo(texto):
    """El GET de MisRx devuelve el tipo de periodo como texto libre (ej. 'mensual
    calendario'), pero el POST lo pide como codigo 0/dias 1/mensual 2/anual.
    Solo esta confirmado el caso 'mensual' contra datos reales - el resto es
    heuristica por palabra clave, puede fallar con textos no vistos todavia."""
    texto = (texto or "").lower()
    for palabra, codigo in _PERIODO_TIPO_TEXTO_A_CODIGO.items():
        if palabra in texto:
            return codigo
    return None


def _payload_desde_snapshot(snapshot):
    """Reconstruye un payload de POST /prescripcion/{convenio_id} a partir de un
    snapshot guardado de GET (estado_anterior) - usado para el rollback."""
    productos = [
        {
            "producto_id": p.get("producto_id"),
            "consumo_cantidad_representa": p.get("consumo_cantidad_representa", 1),
            "porc_cobertura": p.get("porc_cobertura"),
            "repone": p.get("repone", 0),
        }
        for p in (snapshot.get("productos") or [])
    ]
    return {
        "prescripciones_id": snapshot.get("prescripcion_id"),
        "plan_id": snapshot.get("plan_id"),
        "nro_afiliado": snapshot.get("nro_afiliado"),
        "nro_dni": snapshot.get("nro_dni"),
        "monodroga_id": snapshot.get("monodroga_id"),
        "patologia_id": snapshot.get("patologia_id", 0),
        "causa_excepcion_id": snapshot.get("causa_excepcion_id", 0),
        "porc_cobertura": snapshot.get("porc_cobertura"),
        "consumo_cantidad_por_periodo": snapshot.get("consumo_cantidad_por_periodo"),
        "consumo_periodo_tipo": _periodo_tipo_codigo(snapshot.get("consumo_periodo_tipo")),
        "consumo_cantidad_por_receta": snapshot.get("consumo_cantidad_por_receta"),
        "consumo_periodo_dias": snapshot.get("consumo_periodo_dias", 0),
        "fecha_inicio": (snapshot.get("fecha_inicio") or "")[:10],
        "fecha_fin": (snapshot.get("fecha_fin") or "")[:10],
        "productos": productos,
        "baja": 0,
    }


@login_required
@require_POST
def cronicos_rollback(request):
    """Restaura el estado_anterior guardado de un CronicoLog - solo admin, a
    diferencia del resto de /padron/cronicos/ que ya se abrio a Operador."""
    if not request.user.is_superuser:
        return render(request, "403.html", status=403)

    log_original = CronicoLog.objects.filter(pk=request.POST.get("log_id")).first()
    if log_original is None or not log_original.estado_anterior:
        messages.error(request, "No hay un estado anterior guardado para deshacer esa operación.")
        return redirect("padron:cronicos")

    payload = _payload_desde_snapshot(log_original.estado_anterior)
    status_code, respuesta = misrx_client.abm_cronico(payload)
    exitoso = 200 <= status_code < 300

    CronicoLog.objects.create(
        usuario=request.user,
        accion=CronicoLog.ACCION_ROLLBACK,
        dni=log_original.dni,
        nro_afiliado=log_original.nro_afiliado,
        payload_enviado=payload,
        status_code_misrx=status_code,
        respuesta_misrx=json.dumps(respuesta, ensure_ascii=False) if isinstance(respuesta, (dict, list)) else str(respuesta),
        exitoso=exitoso,
    )

    respuesta_fmt = json.dumps(respuesta, ensure_ascii=False) if isinstance(respuesta, (dict, list)) else respuesta
    if exitoso:
        messages.success(request, f"Rollback aplicado sobre la operación #{log_original.id}. MisRx respondió {status_code}: {respuesta_fmt}")
    else:
        messages.error(request, f"MisRx rechazó el rollback ({status_code}): {respuesta_fmt}")

    return redirect(f"{reverse('padron:cronicos')}?dni={log_original.dni}")


@login_required
@require_POST
def cronicos_abm(request):
    if not _puede_gestionar_cronicos(request.user):
        return render(request, "403.html", status=403)

    dni = "".join(ch for ch in request.POST.get("dni", "") if ch.isdigit())
    nro_afiliado = request.POST.get("nro_afiliado", "").strip()
    es_baja = request.POST.get("dar_de_baja") == "on"

    def _num(campo, cast=int, default=None):
        valor = request.POST.get(campo, "").strip()
        if not valor:
            return default
        return cast(valor)

    payload = {
        "plan_id": _num("plan_id"),
        "nro_afiliado": nro_afiliado,
        "nro_dni": _num("nro_dni"),
        "monodroga_id": _num("monodroga_id"),
        "porc_cobertura": _num("porc_cobertura", cast=float),
        "consumo_cantidad_por_periodo": _num("consumo_cantidad_por_periodo"),
        "consumo_periodo_tipo": _num("consumo_periodo_tipo"),
        "consumo_cantidad_por_receta": _num("consumo_cantidad_por_receta"),
        "consumo_periodo_dias": _num("consumo_periodo_dias", default=0),
        "fecha_inicio": request.POST.get("fecha_inicio", "").strip(),
        "fecha_fin": request.POST.get("fecha_fin", "").strip(),
        "productos": [{
            "producto_id": _num("producto_id"),
            "consumo_cantidad_representa": _num("consumo_cantidad_representa", default=1),
            "porc_cobertura": _num("porc_cobertura", cast=float),
            "repone": _num("repone", default=0),
        }],
    }
    prescripciones_id = _num("prescripciones_id")
    if prescripciones_id:
        payload["prescripciones_id"] = prescripciones_id
    if es_baja:
        payload["baja"] = 1

    # Dar de alta/editar cobertura cronica para alguien que GX no marca Activo
    # no tiene sentido (no esta cubierto); la baja de un registro existente si
    # se permite igual, incluso sobre un afiliado ya inactivo.
    if not es_baja:
        afiliado_gx = gx_query.buscar_afiliado_por_dni(dni) if dni else None
        if afiliado_gx is None or not afiliado_gx["activo"]:
            estado_gx = afiliado_gx["estado"] if afiliado_gx else "no encontrado en GX"
            CronicoLog.objects.create(
                usuario=request.user,
                accion=CronicoLog.ACCION_ALTA,
                dni=dni,
                nro_afiliado=nro_afiliado,
                payload_enviado=payload,
                respuesta_misrx=f"BLOQUEADO sin llamar a MisRx: afiliado no esta Activo en GX (estado: {estado_gx})",
                exitoso=False,
            )
            messages.error(
                request,
                f"No se envio nada a MisRx: el afiliado no figura Activo en GX (estado: {estado_gx}). "
                "Solo se permite dar de baja un registro ya existente para alguien inactivo.",
            )
            return redirect(f"{reverse('padron:cronicos')}?dni={dni}")

    # Snapshot de "antes" para poder reconstruir un rollback a mano si esta
    # edicion/baja termina siendo un error - se pierde si no se guarda ahora,
    # MisRx no expone un historial de cambios de una prescripcion.
    estado_anterior = None
    if prescripciones_id:
        try:
            actuales = misrx_client.consultar_cronicos(nro_afiliado).get("data") or []
            estado_anterior = next(
                (p for p in actuales if p.get("prescripcion_id") == prescripciones_id), None
            )
        except Exception:
            estado_anterior = None

    status_code, respuesta = misrx_client.abm_cronico(payload)
    exitoso = 200 <= status_code < 300

    CronicoLog.objects.create(
        usuario=request.user,
        accion=CronicoLog.ACCION_BAJA if es_baja else CronicoLog.ACCION_ALTA,
        dni=dni,
        nro_afiliado=nro_afiliado,
        estado_anterior=estado_anterior,
        payload_enviado=payload,
        status_code_misrx=status_code,
        respuesta_misrx=json.dumps(respuesta, ensure_ascii=False) if isinstance(respuesta, (dict, list)) else str(respuesta),
        exitoso=exitoso,
    )

    respuesta_fmt = json.dumps(respuesta, ensure_ascii=False) if isinstance(respuesta, (dict, list)) else respuesta
    if exitoso:
        messages.success(request, f"MisRx respondio {status_code}: {respuesta_fmt}")
    else:
        messages.error(request, f"MisRx devolvio un error ({status_code}): {respuesta_fmt}")

    return redirect(f"{reverse('padron:cronicos')}?dni={dni}")


@login_required
@require_POST
def cronicos_vademecum_actualizar(request):
    if not _puede_gestionar_cronicos(request.user):
        return render(request, "403.html", status=403)

    archivo = request.FILES.get("archivo")
    link = request.POST.get("link", "").strip()

    try:
        if archivo:
            origen = f"archivo subido ({archivo.name})"
            total = vademecum.cargar_desde_bytes(archivo.read())
        else:
            origen = f"link: {link}" if link else "fuente por defecto"
            total = vademecum.descargar_y_cargar(url=link or None)
        messages.success(request, f"Vademécum actualizado desde {origen}: {total} productos.")
        AuditLogEntry.objects.create(
            usuario=request.user,
            accion=AuditLogEntry.ACCION_VADEMECUM_ACTUALIZADO,
            ip_address=_client_ip(request),
            detalle=f"{origen} - {total} productos"[:255],
        )
    except Exception as e:
        messages.error(request, f"Error actualizando el vademécum: {e}")

    return redirect("padron:cronicos")


@login_required
def cronicos_buscar_monodroga(request):
    if not _puede_gestionar_cronicos(request.user):
        return JsonResponse({"error": "forbidden"}, status=403)
    resultados = vademecum.buscar_monodroga(request.GET.get("q", "").strip())
    return JsonResponse({"resultados": resultados})


@login_required
def cronicos_buscar_producto(request):
    if not _puede_gestionar_cronicos(request.user):
        return JsonResponse({"error": "forbidden"}, status=403)
    texto = request.GET.get("q", "").strip()
    monodroga_id = request.GET.get("monodroga_id", "").strip() or None
    resultados = vademecum.buscar_producto(texto, monodroga_id=monodroga_id)
    return JsonResponse({"resultados": resultados})


@login_required
def cronicos_buscar_patologia(request):
    if not _puede_gestionar_cronicos(request.user):
        return JsonResponse({"error": "forbidden"}, status=403)
    texto = request.GET.get("q", "").strip().lower()
    try:
        patologias = misrx_client.consultar_patologias()
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=502)
    if len(texto) < 2:
        resultados = []
    else:
        resultados = [
            {"id": p["patologia_id"], "nombre": p["descripcion"]}
            for p in patologias
            if texto in p["descripcion"].lower()
        ][:20]
    return JsonResponse({"resultados": resultados})
