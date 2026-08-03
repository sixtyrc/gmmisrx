"""Cliente de la API de MisRx (Basic Auth)."""
import os

import requests


def _config():
    return {
        "base_url": os.environ["MISRX_BASE_URL"],
        "auth": (os.environ["MISRX_USER"], os.environ["MISRX_PASSWORD"]),
        "convenio_id": os.environ["MISRX_CONVENIO_ID"],
    }


def subir_padron(contenido_bytes, nombre_archivo):
    cfg = _config()
    url = f"{cfg['base_url']}/padrones/cargar/{cfg['convenio_id']}"
    resp = requests.post(
        url,
        auth=cfg["auth"],
        files={"archivo": (nombre_archivo, contenido_bytes, "text/csv")},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def obtener_ultimo_registro():
    """Ultima entrada del historial de cargas para este convenio (para verificar el estado procesado)."""
    cfg = _config()
    url = f"{cfg['base_url']}/padrones/registros/{cfg['convenio_id']}"
    resp = requests.get(url, auth=cfg["auth"], params={"limit": 1}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    registros = data.get("data") or []
    return registros[0] if registros else None
