from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from padron.models import PadronRun
from padron.services.pipeline import ejecutar_actualizacion


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
        usuario = None
        if options["trigger"] == PadronRun.TRIGGER_AUTOMATICO:
            usuario = get_user_model().objects.filter(username="automatizacion").first()

        run = ejecutar_actualizacion(
            trigger=options["trigger"],
            usuario=usuario,
            dry_run=options["dry_run"],
        )
        self.stdout.write(self.style.SUCCESS(
            f"OK - {run.total_enviado_misrx} registros, altas={run.altas_count}, bajas={run.bajas_count}"
        ))
