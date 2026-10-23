from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from padron.services import vademecum
from padron.services.archivos import ArchivoInvalido, leer_validado

XLSX_FALSO = b"PK\x03\x04" + b"0" * 100


class LeerValidadoTests(SimpleTestCase):
    def test_acepta_xlsx_valido(self):
        archivo = SimpleUploadedFile("padron.xlsx", XLSX_FALSO)
        self.assertEqual(leer_validado(archivo, (".xlsx",)), XLSX_FALSO)

    def test_rechaza_extension_no_permitida(self):
        archivo = SimpleUploadedFile("script.exe", XLSX_FALSO)
        with self.assertRaises(ArchivoInvalido):
            leer_validado(archivo, (".xlsx",))

    def test_rechaza_xlsx_con_contenido_falso(self):
        archivo = SimpleUploadedFile("padron.xlsx", b"<html>no soy excel</html>")
        with self.assertRaises(ArchivoInvalido):
            leer_validado(archivo, (".xlsx",))

    def test_rechaza_archivo_grande(self):
        archivo = SimpleUploadedFile("padron.xlsx", XLSX_FALSO)
        with self.assertRaises(ArchivoInvalido):
            leer_validado(archivo, (".xlsx",), tamano_maximo=10)

    def test_csv_texto_ok_y_binario_rechazado(self):
        self.assertTrue(leer_validado(SimpleUploadedFile("a.csv", b"Nro Documento;x\n1;2"), (".csv",)))
        with self.assertRaises(ArchivoInvalido):
            leer_validado(SimpleUploadedFile("a.csv", b"\x00\x01\x02"), (".csv",))


class VademecumUrlTests(SimpleTestCase):
    @patch("padron.services.vademecum.requests.get")
    def test_rechaza_urls_fuera_de_google_sheets(self, mock_get):
        for url in ("http://example.com/vademecum.xlsx", "https://169.254.169.254/latest",
                    "https://localhost:8000/admin", "https://docs.google.com.evil.com/x"):
            with self.assertRaises(ArchivoInvalido, msg=url):
                vademecum.descargar_y_cargar(url=url)
        mock_get.assert_not_called()

    def test_link_de_google_sheets_es_aceptado(self):
        url = vademecum.normalizar_url_google_sheets("https://docs.google.com/spreadsheets/d/abc123/edit#gid=0")
        vademecum.validar_url(url)
