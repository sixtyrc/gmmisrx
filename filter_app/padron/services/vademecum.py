"""Catalogo Alfabeta (producto/monodroga) para resolver nombre -> ID sin tener
que conocerlos de memoria. Fuente: planilla de Google Sheets del usuario,
verificada exacta contra los codigos reales que ya usa MisRx (ver
docs/REFERENCIA_API_MISRX.md seccion 4)."""
import io
import re

import openpyxl
import requests

from ..models import VademecumItem

URL_VADEMECUM = "https://docs.google.com/spreadsheets/d/1lFNnjCyr6mkf46TZl0_eYn3BOlvfLdO8/export?format=xlsx"

RESULTADOS_MAX = 20


def normalizar_url_google_sheets(url):
    """Si es un link normal de Google Sheets (el que se copia del navegador),
    lo convierte al formato de descarga .xlsx. Cualquier otra URL se usa tal cual."""
    match = re.search(r"docs\.google\.com/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    if match:
        return f"https://docs.google.com/spreadsheets/d/{match.group(1)}/export?format=xlsx"
    return url


def descargar_y_cargar(url=None):
    """Baja la planilla (por defecto la de `URL_VADEMECUM`, o la URL indicada) y
    reemplaza el contenido de VademecumItem por completo."""
    resp = requests.get(normalizar_url_google_sheets(url) if url else URL_VADEMECUM, timeout=120)
    resp.raise_for_status()
    return cargar_desde_bytes(resp.content)


def cargar_desde_bytes(contenido_bytes):
    """Reemplaza el contenido de VademecumItem por completo a partir de un .xlsx
    ya en memoria (subido a mano o descargado)."""
    wb = openpyxl.load_workbook(io.BytesIO(contenido_bytes), read_only=True, data_only=True)
    ws = wb["Pag1"]

    items = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or row[0] is None:
            continue
        try:
            producto_id = int(row[0])
            monodroga_id = int(row[8]) if len(row) > 8 and row[8] is not None else None
        except (TypeError, ValueError):
            continue
        if monodroga_id is None:
            continue
        items.append(VademecumItem(
            producto_id=producto_id,
            nombre_producto=(row[1] or "").strip(),
            presentacion=(row[2] or "").strip(),
            laboratorio=(row[3] or "").strip(),
            troquel=str(row[4]).strip() if row[4] is not None else "",
            codigobarra=(row[5] or "").strip() if len(row) > 5 else "",
            monodroga_id=monodroga_id,
            monodroga_nombre=(row[9] or "").strip() if len(row) > 9 else "",
            potencia=(row[11] or "").strip() if len(row) > 11 else "",
        ))

    VademecumItem.objects.all().delete()
    VademecumItem.objects.bulk_create(items, batch_size=2000, ignore_conflicts=True)
    return len(items)


def estadisticas():
    total = VademecumItem.objects.count()
    ultimo = VademecumItem.objects.order_by("-actualizado_en").values_list("actualizado_en", flat=True).first()
    return {"total": total, "actualizado_en": ultimo}


def buscar_monodroga(texto):
    if not texto or len(texto) < 3:
        return []
    qs = (
        VademecumItem.objects
        .filter(monodroga_nombre__icontains=texto)
        .order_by("monodroga_nombre")
        .values_list("monodroga_id", "monodroga_nombre")
        .distinct()
    )
    vistos = {}
    for monodroga_id, nombre in qs:
        if monodroga_id not in vistos:
            vistos[monodroga_id] = nombre
        if len(vistos) >= RESULTADOS_MAX:
            break
    return [{"id": mid, "nombre": nombre} for mid, nombre in vistos.items()]


def buscar_producto(texto, monodroga_id=None):
    qs = VademecumItem.objects.all()
    if monodroga_id:
        qs = qs.filter(monodroga_id=monodroga_id)
    if texto and len(texto) >= 3:
        qs = qs.filter(nombre_producto__icontains=texto)
    elif not monodroga_id:
        return []
    qs = qs.order_by("nombre_producto")[:RESULTADOS_MAX]
    return [
        {
            "id": item.producto_id,
            "nombre": item.nombre_producto,
            "presentacion": item.presentacion,
            "laboratorio": item.laboratorio,
        }
        for item in qs
    ]
