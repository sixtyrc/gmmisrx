"""Orquesta el proceso completo de actualizacion del padron. Usado tanto por el
management command (tarea programada) como por el boton 'Ejecutar ahora' del panel."""
import os
from datetime import datetime, timezone

from django.conf import settings

from padron.models import PadronRun

from . import csv_builder, gx_query, misrx_client, notificaciones

ARCHIVOS_DIR = os.path.join(settings.BASE_DIR, "padron_archivos")


def ejecutar_actualizacion(trigger, usuario=None, dry_run=False):
    """Corre el pipeline completo y devuelve el PadronRun resultante.

    trigger: PadronRun.TRIGGER_AUTOMATICO o PadronRun.TRIGGER_MANUAL
    usuario: instancia de User a asociar a la corrida (quien la disparo)
    """
    os.makedirs(ARCHIVOS_DIR, exist_ok=True)
    run = PadronRun.objects.create(disparado_por=trigger, usuario=usuario)

    try:
        convenios = [c.strip() for c in os.environ["CONVENIOS_VALIDOS"].split(",")]
        filas = gx_query.obtener_padron_vigente(convenios)
        run.total_consulta_gx = len(filas)

        dnis_actuales = sorted(str(f["dni"]) for f in filas)
        registros_actuales = [
            {
                "dni": str(f["dni"]),
                "nro_afiliado": f.get("nro_afiliado"),
                "nombres": f.get("nombres"),
                "apellido": f.get("apellido"),
            }
            for f in filas
        ]
        contenido = csv_builder.construir_csv(filas)
        nombre = csv_builder.nombre_archivo()

        with open(os.path.join(ARCHIVOS_DIR, nombre), "wb") as fh:
            fh.write(contenido)

        corrida_anterior = (
            PadronRun.objects.filter(estado=PadronRun.ESTADO_OK)
            .exclude(pk=run.pk)
            .order_by("-iniciado_en")
            .first()
        )
        if corrida_anterior is not None:
            dnis_previos = set(corrida_anterior.dnis_incluidos)
            dnis_actuales_set = set(dnis_actuales)
            dnis_alta = dnis_actuales_set - dnis_previos
            dnis_baja = dnis_previos - dnis_actuales_set

            run.altas_count = len(dnis_alta)
            run.bajas_count = len(dnis_baja)
            run.altas_detalle = [r for r in registros_actuales if r["dni"] in dnis_alta]

            # El detalle de las bajas sale del snapshot de la corrida ANTERIOR (ya
            # no estan en la actual, asi que no hay de donde mas sacar su nombre).
            # Si esa corrida anterior es previa a este campo, va a estar vacio y la
            # baja queda sin detalle (solo el conteo).
            registros_previos_por_dni = {
                r["dni"]: r for r in (corrida_anterior.registros_incluidos or [])
            }
            run.bajas_detalle = [
                registros_previos_por_dni[dni] for dni in dnis_baja if dni in registros_previos_por_dni
            ]

        if not dry_run:
            misrx_client.subir_padron(contenido, nombre)
            ultimo = misrx_client.obtener_ultimo_registro()
            if ultimo:
                run.misrx_padrones_registros_id = ultimo.get("padrones_registros_id")
                run.misrx_estado_descripcion = ultimo.get("padrones_procesa_estado_descripcion", "")
                run.misrx_info = ultimo.get("info", "")
        else:
            run.misrx_estado_descripcion = "DRY RUN - no se subio a MisRx"

        run.total_enviado_misrx = len(filas)
        run.archivo_generado = nombre
        run.dnis_incluidos = dnis_actuales
        run.registros_incluidos = registros_actuales
        run.estado = PadronRun.ESTADO_OK
        run.finalizado_en = datetime.now(timezone.utc)
        run.save()

        notificaciones.notificar_resultado(run)
        return run

    except Exception as e:
        run.estado = PadronRun.ESTADO_ERROR
        run.error_mensaje = str(e)
        run.finalizado_en = datetime.now(timezone.utc)
        run.save()
        notificaciones.notificar_resultado(run)
        raise
