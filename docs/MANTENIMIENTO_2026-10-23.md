# Mantenimiento 2026-10-23

Cambios hechos en `dev`, probados y pasados a `prod` el mismo día. Versión resultante: 1.0.2 en adelante.

## 1. Dependencias con vulnerabilidades

| Componente | Antes | Después | Motivo |
|---|---|---|---|
| Django | 6.0.7 | 6.0.9 | CVE-2026-84429 / 87975 / 87890 / 77050 (Alta) |
| certifi | 2026.7.22 | 2026.10.19 | Remoción de las CA emSign/eMudhra (Alta) |
| pip (y su certifi interno) | 26.1.2 | 26.2.2 | Mismo motivo que certifi (Alta) |

- `filter_app/requirements.txt` actualizado.
- El deploy ahora corre `python -m pip install --upgrade "pip>=26.2.2"` antes de instalar dependencias, así el venv del server queda al día solo.
- Verificado en el server: `6.0.9 2026.10.19` y `pip 26.2.2`.

## 2. Logo roto

La URL externa del logo (`ss-static-01.esmsv.com/.../obtenerimagen/...`) empezó a devolver 404. Se bajó el logo oficial de gmsalud.com a `filter_app/padron/static/padron/logo.png` y las 5 pantallas (login, dashboard, consumos, crónicos, 403) lo sirven con `{% static %}`. Ya no depende de un sitio externo.

## 3. Validación de archivos subidos

El reporte lo marcaba como Info: las dos pantallas de carga requieren login y permisos, pero el servidor no validaba lo que recibía.

Nuevo módulo `filter_app/padron/services/archivos.py`, usado por:
- Herramienta legacy (`processor/views.py`, Excel + CSV).
- Vademécum de crónicos (`padron/views.py` y `padron/services/vademecum.py`).

Reglas:
- Tamaño máximo 10 MB.
- Extensión permitida (`.xlsx`/`.xls` o `.csv`) y contenido real verificado por firma (un `.xlsx` es un ZIP, un `.xls` es OLE2, un CSV no puede tener bytes nulos).
- El link del vademécum solo acepta `https://docs.google.com/...` y corta la descarga si supera 10 MB. Evita que el servidor descargue URLs arbitrarias, incluidas direcciones de la red interna.

Tests: `filter_app/padron/tests_archivos.py` (7 tests).

## 4. Versionado semántico automático

`filter_app/version.txt`, visible en el login. Se sube solo en cada deploy a `prod`. Detalle en [DEPLOY.md](./DEPLOY.md#versionado).

## Pendientes

- CSP y Permissions-Policy (ver [REVISION_SEGURIDAD_2026-10-10](./REVISION_SEGURIDAD_2026-10-10.md)).
- Probar en prod una actualización real del vademécum desde el link de Google Sheets.
- La suite de tests es chica (10 tests); conviene sumar cobertura antes de cambios grandes.
