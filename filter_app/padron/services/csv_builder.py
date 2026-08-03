"""Genera el CSV con el mismo formato exacto que produce hoy el reporte de GeneXus
(WPMisRxAfiliadosExportCSV4), para que MisRx lo acepte sin cambios."""
from datetime import datetime

HEADER = "Nro Documento;Nro Afiliado;Nombres;Apellido;Sexo;Fecha Nacimiento;PMI;Oncologico;PlanCodigo;Plan"

SEXO_MAP = {"F": "Femenino", "M": "Masculino", "O": "Otro"}


def _sanitizar_texto(valor):
    if valor is None:
        return ""
    return str(valor).replace(";", ",").replace("\r", " ").replace("\n", " ").strip()


def _fila_a_linea(fila):
    sexo = SEXO_MAP.get(str(fila["sexo"]).strip(), "") if fila["sexo"] else ""
    # GeneXus muestra el codigo fuente como "yyyy/mm/dd", pero el separador real que
    # emite el server (segun su configuracion regional) es "-", confirmado contra
    # un CSV real bajado de GX hoy (ej. "2016-04-19"). Se replica el formato real, no el literal.
    fecha_nac = fila["fecha_nacimiento"].strftime("%Y-%m-%d") if fila["fecha_nacimiento"] else ""
    pmi = "1" if str(fila["pmi"]).strip() == "S" else "0"
    oncologico = "1" if str(fila["oncologico"]).strip() == "S" else "0"

    campos = [
        str(fila["dni"]).strip(),
        str(fila["nro_afiliado"]).strip(),
        _sanitizar_texto(fila["nombres"]),
        _sanitizar_texto(fila["apellido"]),
        sexo,
        fecha_nac,
        pmi,
        oncologico,
        str(fila["plan_codigo"]).strip(),
        _sanitizar_texto(fila["plan_descripcion"]),
    ]
    return ";".join(campos)


def construir_csv(filas):
    """Devuelve el contenido del CSV como bytes (utf-8-sig, igual que el proceso manual ya validado con MisRx)."""
    lineas = [HEADER] + [_fila_a_linea(f) for f in filas]
    contenido = "\r\n".join(lineas) + "\r\n"
    return contenido.encode("utf-8-sig")


def nombre_archivo():
    ahora = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"AfiliadoGM_Ospena_{ahora}.csv"
