import os
from datetime import datetime, timezone

from django.conf import settings
from django.core.management.base import BaseCommand

from padron.models import PadronRun
from padron.services import csv_builder, gx_query, misrx_client, notificaciones

ARCHIVOS_DIR = os.path.join(settings.BASE_DIR, "padron_archivos")


class Command(BaseCommand):
    help = "Consulta el padron vigente en GX, lo sube a MisRx, verifica el resultado y notifica."

    def add_arguments(self, parser):
        parser.add_argument(
            "--trigger",
            choices=[PadronRun.TRIGGER_AUTOMATICO, PadronRun.TRIGGER_MANUAL],
            default=PadronRun.TRIGGER_MANUAL,
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Genera el archivo y calcula todo, pero no lo sube a MisRx.",
        )

    def handle(self, *args, **options):
        os.makedirs(ARCHIVOS_DIR, exist_ok=True)
        run = PadronRun.objects.create(disparado_por=options["trigger"])

        try:
            convenios = [c.strip() for c in os.environ["CONVENIOS_VALIDOS"].split(",")]
            filas = gx_query.obtener_padron_vigente(convenios)
            run.total_consulta_gx = len(filas)

            dnis_actuales = sorted(str(f["dni"]) for f in filas)
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
                run.altas_count = len(set(dnis_actuales) - dnis_previos)
                run.bajas_count = len(dnis_previos - set(dnis_actuales))

            if not options["dry_run"]:
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
            run.estado = PadronRun.ESTADO_OK
            run.finalizado_en = datetime.now(timezone.utc)
            run.save()

            notificaciones.notificar_resultado(run)
            self.stdout.write(self.style.SUCCESS(
                f"OK - {run.total_enviado_misrx} registros, altas={run.altas_count}, bajas={run.bajas_count}"
            ))

        except Exception as e:
            run.estado = PadronRun.ESTADO_ERROR
            run.error_mensaje = str(e)
            run.finalizado_en = datetime.now(timezone.utc)
            run.save()
            notificaciones.notificar_resultado(run)
            raise
