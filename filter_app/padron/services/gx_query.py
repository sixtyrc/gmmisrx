"""Consulta de solo lectura a la Postgres de GeneXus (rol misrx_padron_ro)."""
import os

import psycopg2

# Reemplaza el cruce manual Excel/CSV: se queda con el registro de Afiliado mas
# reciente por persona (IndividuoId), y lo incluye solo si esta activo y su
# convenio esta en la lista de convenios validos. Validado contra la base real:
# incluye automaticamente los casos de gente con un registro viejo en OSFOT y
# uno nuevo en NAV (antes se excluian por error via el cruce manual por DNI).
QUERY_PADRON_VIGENTE = """
WITH afiliado_vigente AS (
    SELECT DISTINCT ON (a.IndividuoId)
        a.AfiliadoId, a.IndividuoId, a.PlanId,
        a.AfiliadoEstado, a.AfiliadoConvenio, a.AfiliadoBaja,
        a.AfiliadoFechaAlta, a.AfiliadoPMI, a.AfiliadoOncologico
    FROM Afiliado a
    ORDER BY a.IndividuoId, a.AfiliadoFechaAlta DESC
)
SELECT
    i.IndividuoDNI      AS dni,
    v.AfiliadoId        AS nro_afiliado,
    i.IndividuoNombre   AS nombres,
    i.IndividuoApellido AS apellido,
    i.IndividuoSexo     AS sexo,
    i.IndividuoFecNac   AS fecha_nacimiento,
    v.AfiliadoPMI       AS pmi,
    v.AfiliadoOncologico AS oncologico,
    p.PlanCodigoMisrx   AS plan_codigo,
    p.PlanDescripcion   AS plan_descripcion
FROM afiliado_vigente v
JOIN Individuo i ON i.IndividuoId = v.IndividuoId
JOIN Plan p       ON p.PlanId = v.PlanId
WHERE v.AfiliadoEstado = 'ACT'
  AND v.AfiliadoBaja = 'N'
  AND v.AfiliadoConvenio = ANY(%s)
ORDER BY i.IndividuoDNI
"""


def _conexion():
    return psycopg2.connect(
        host=os.environ["GX_DB_HOST"],
        port=os.environ["GX_DB_PORT"],
        dbname=os.environ["GX_DB_NAME"],
        user=os.environ["GX_DB_USER"],
        password=os.environ["GX_DB_PASSWORD"],
        options="-c client_encoding=UTF8",
        connect_timeout=15,
    )


def obtener_padron_vigente(convenios_validos):
    """Devuelve una lista de dicts con el padron vigente segun la regla de convenio/alta mas reciente."""
    conn = _conexion()
    try:
        cur = conn.cursor()
        cur.execute(QUERY_PADRON_VIGENTE, (list(convenios_validos),))
        columnas = [d.name for d in cur.description]
        filas = [dict(zip(columnas, row)) for row in cur.fetchall()]
        return filas
    finally:
        conn.close()


# La API de MisRx no acepta DNI como filtro en /prescripcion (solo nro_afiliado
# o prescripcion_id) - se resuelve DNI -> AfiliadoId contra GX antes de consultarla.
QUERY_AFILIADO_POR_DNI = """
SELECT DISTINCT ON (a.IndividuoId)
    i.IndividuoDNI      AS dni,
    a.AfiliadoId        AS nro_afiliado,
    i.IndividuoNombre   AS nombres,
    i.IndividuoApellido AS apellido,
    a.AfiliadoEstado    AS estado,
    (a.AfiliadoEstado = 'ACT' AND a.AfiliadoBaja = 'N') AS activo,
    a.AfiliadoConvenio  AS convenio,
    p.PlanCodigoMisrx   AS plan_codigo
FROM Afiliado a
JOIN Individuo i ON i.IndividuoId = a.IndividuoId
JOIN Plan p       ON p.PlanId = a.PlanId
WHERE i.IndividuoDNI = %s
ORDER BY a.IndividuoId, a.AfiliadoFechaAlta DESC
"""


def buscar_afiliado_por_dni(dni):
    """Devuelve el registro de Afiliado mas reciente para ese DNI (cualquier estado/convenio), o None."""
    conn = _conexion()
    try:
        cur = conn.cursor()
        cur.execute(QUERY_AFILIADO_POR_DNI, (dni,))
        fila = cur.fetchone()
        if fila is None:
            return None
        columnas = [d.name for d in cur.description]
        return dict(zip(columnas, fila))
    finally:
        conn.close()
