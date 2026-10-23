"""Validacion de archivos subidos por usuarios (Excel / CSV) antes de procesarlos.

El `accept` del <input> solo filtra en el navegador; aca se valida del lado del
servidor: tamano maximo, extension y contenido real (firma del archivo)."""
import os

TAMANO_MAXIMO = 10 * 1024 * 1024  # 10 MB

# Firmas (magic bytes): .xlsx es un ZIP, .xls es un documento OLE2.
FIRMA_XLSX = b"PK\x03\x04"
FIRMA_XLS = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


class ArchivoInvalido(ValueError):
    pass


def leer_validado(archivo, extensiones, tamano_maximo=TAMANO_MAXIMO):
    """Valida un UploadedFile y devuelve su contenido en bytes.

    `extensiones`: tupla como (".xlsx",) o (".csv",). Lanza ArchivoInvalido con
    un mensaje apto para mostrar al usuario."""
    nombre = archivo.name or ""
    ext = os.path.splitext(nombre)[1].lower()
    if ext not in extensiones:
        raise ArchivoInvalido(f"El archivo \"{nombre}\" debe ser {' o '.join(extensiones)}.")
    if archivo.size > tamano_maximo:
        raise ArchivoInvalido(f"El archivo \"{nombre}\" supera el máximo de {tamano_maximo // (1024 * 1024)} MB.")

    contenido = archivo.read()
    validar_contenido(contenido, ext, nombre)
    return contenido


def validar_contenido(contenido, ext, nombre="archivo"):
    if ext == ".xlsx" and not contenido.startswith(FIRMA_XLSX):
        raise ArchivoInvalido(f"\"{nombre}\" no es un Excel .xlsx válido.")
    if ext == ".xls" and not contenido.startswith(FIRMA_XLS):
        raise ArchivoInvalido(f"\"{nombre}\" no es un Excel .xls válido.")
    if ext == ".csv" and b"\x00" in contenido[:8192]:
        raise ArchivoInvalido(f"\"{nombre}\" no es un CSV de texto válido.")
