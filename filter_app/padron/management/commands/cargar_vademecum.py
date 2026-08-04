from django.core.management.base import BaseCommand

from padron.services import vademecum


class Command(BaseCommand):
    help = "Descarga el vademecum Alfabeta (Google Sheets) y refresca VademecumItem por completo."

    def handle(self, *args, **options):
        total = vademecum.descargar_y_cargar()
        self.stdout.write(self.style.SUCCESS(f"OK - {total} productos cargados"))
