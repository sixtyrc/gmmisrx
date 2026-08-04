"""Cliente de la API de MisRx (Basic Auth)."""
import os
import re

import requests

_CUPON_HREF_RE = re.compile(r'href="([^"]+)"')


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


def consultar_cronicos(nro_afiliado):
    """Prescripciones cronicas cargadas en MisRx para un nro de afiliado."""
    cfg = _config()
    url = f"{cfg['base_url']}/prescripcion/{cfg['convenio_id']}"
    resp = requests.get(url, auth=cfg["auth"], params={"nroafiliado": nro_afiliado}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def consultar_patologias():
    """Catalogo de patologias del convenio (para el ABM de cronicos)."""
    cfg = _config()
    url = f"{cfg['base_url']}/patologias/{cfg['convenio_id']}"
    resp = requests.get(url, auth=cfg["auth"], timeout=30)
    resp.raise_for_status()
    return resp.json().get("data") or []


def consultar_consumo(dni):
    """Recetas validadas de un afiliado (consulta predefinida 14, "Afiliado
    Consumo Detallado" - ver docs/REFERENCIA_API_MISRX.md seccion 8). A
    diferencia de /prescripcion, esta se filtra directo por DNI, no hace
    falta resolver nro_afiliado contra GX primero."""
    cfg = _config()
    url = f"{cfg['base_url']}/consultas/consultar/14"
    payload = {"convenio_id": int(cfg["convenio_id"]), "nro_afiliado_dni": dni}
    resp = requests.post(url, auth=cfg["auth"], json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def normalizar_item_consumo(fila):
    """La clave 'Fecha Prescripcion' viene con un caracter invalido de encoding
    del lado de MisRx (confirmado en vivo, no es un typo nuestro) - se busca
    por prefijo en vez de nombre exacto. El campo 'cupon' trae HTML armado por
    MisRx (un <a>); se extrae solo la URL para no tener que renderizar HTML
    ajeno con |safe en el template."""
    fecha_prescripcion = next(
        (v for k, v in fila.items() if k.startswith("Fecha") and k != "Fecha_Validacion"),
        None,
    )
    cupon_match = _CUPON_HREF_RE.search(fila.get("cupon") or "")
    return {
        "cod_validacion": fila.get("Cod_Validacion"),
        "recetario": fila.get("Recetario"),
        "recetario_asignado": fila.get("Recetario Asignado"),
        "fecha_validacion": fila.get("Fecha_Validacion"),
        "fecha_prescripcion": fecha_prescripcion,
        "producto": fila.get("Producto"),
        "presentacion": fila.get("Presentacion"),
        "unidades": fila.get("Unidades"),
        "cuf": fila.get("CUF"),
        "farmacia_nombre": fila.get("Farmacia_Nombre"),
        "farmacia_cuit": fila.get("Farmacia_CUIT"),
        "nro_doc": fila.get("Nro_Doc"),
        "nro_afiliado": fila.get("Nro_Afiliado"),
        "afiliado": fila.get("Afiliado"),
        "medico_nombre": fila.get("Medico_Nombre"),
        "medico_matricula": fila.get("Medico_Matricula"),
        "medico_tipo_matricula": fila.get("Medico_Tipo_Matricula"),
        "nro_item_receta": fila.get("Nro_Item_Receta"),
        "laboratorio": fila.get("Laboratorio"),
        "monodroga": fila.get("Monodroga"),
        "troquel": fila.get("Troquel"),
        "codigo_barra": fila.get("Codigo_Barra"),
        "pvp": fila.get("PVP"),
        "total_pvp": fila.get("Total_PVP"),
        "porc_cobertura": fila.get("Porc_Cobertura"),
        "cobertura": fila.get("Cobertura"),
        "plan": fila.get("plan"),
        "estado": fila.get("Estado"),
        "cupon_url": cupon_match.group(1) if cupon_match else None,
    }


def abm_cronico(payload):
    """Alta/edicion/baja de una prescripcion cronica (ABM sobre /prescripcion).

    No usa raise_for_status: el body de error de MisRx trae el detalle util
    (campos invalidos, etc.) y hay que poder mostrarlo tal cual en el panel.
    Devuelve (status_code, body_dict_o_texto).
    """
    cfg = _config()
    url = f"{cfg['base_url']}/prescripcion/{cfg['convenio_id']}"
    resp = requests.post(url, auth=cfg["auth"], json=payload, timeout=30)
    try:
        body = resp.json()
    except ValueError:
        body = resp.text
    return resp.status_code, body
