"""Nombres amigables para los codigos internos de convenio de GeneXus.

FOT y NAV son los codigos internos que usa GX (AfiliadoConvenio) para
identificar el convenio del afiliado. Para el operador se conocen como
OSFOT y OSPENA - usar nombre_convenio() en cualquier pantalla o reporte
que le muestre este dato a un usuario.
"""
NOMBRES_CONVENIO = {
    "FOT": "OSFOT",
    "NAV": "OSPENA",
}


def nombre_convenio(codigo):
    if not codigo:
        return codigo
    return NOMBRES_CONVENIO.get(codigo, codigo)
