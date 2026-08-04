"""Nombres conocidos de "planes especiales" de MisRx (el `plan` que devuelve
cada receta en /consultas/consultar/14 - un id interno de MisRx, distinto del
plan de cobertura real del afiliado en el padron).

Hoy solo esta confirmado el de Prescripciones Cronicas (ver
docs/REFERENCIA_API_MISRX.md seccion 4: plan_id 1939, cobertura 100%).
Si se confirma el id de otro plan especial (ej. anticonceptivos, que tambien
suele cubrirse al 100% en muchas obras sociales) agregarlo aca - no hay forma
de saberlo sin verlo en una receta real con ese plan o preguntandole a
soporte Preserfar, no inventar un numero."""
NOMBRES_PLAN_ESPECIAL = {
    1939: "Crónicos",
}


def nombre_plan(plan_id):
    if plan_id is None:
        return None
    try:
        return NOMBRES_PLAN_ESPECIAL.get(int(plan_id))
    except (TypeError, ValueError):
        return None
