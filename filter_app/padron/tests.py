from unittest.mock import patch

from django.test import TestCase

from padron.models import PadronRun
from padron.services.pipeline import ejecutar_actualizacion

FILA_ANA = {
    "dni": "111", "nro_afiliado": "1001", "nombres": "Ana", "apellido": "Perez",
    "sexo": "F", "fecha_nacimiento": None, "pmi": "N", "oncologico": "N",
    "plan_codigo": "1", "plan_descripcion": "Plan A",
}
FILA_LUIS = {
    "dni": "222", "nro_afiliado": "1002", "nombres": "Luis", "apellido": "Gomez",
    "sexo": "M", "fecha_nacimiento": None, "pmi": "N", "oncologico": "N",
    "plan_codigo": "1", "plan_descripcion": "Plan A",
}
FILA_MARTA = {
    "dni": "333", "nro_afiliado": "1003", "nombres": "Marta", "apellido": "Diaz",
    "sexo": "F", "fecha_nacimiento": None, "pmi": "N", "oncologico": "N",
    "plan_codigo": "1", "plan_descripcion": "Plan A",
}

CORRIDA_1 = [FILA_ANA, FILA_LUIS]
CORRIDA_2 = [FILA_ANA, FILA_MARTA]  # Luis se da de baja, Marta es alta


def _mockear_misrx(mock_subir, mock_ultimo):
    mock_subir.return_value = {"ok": True}
    mock_ultimo.return_value = {
        "padrones_registros_id": 1,
        "padrones_procesa_estado_descripcion": "Padron procesado correctamente",
        "info": "",
    }


@patch("padron.services.pipeline.misrx_client.obtener_ultimo_registro")
@patch("padron.services.pipeline.misrx_client.subir_padron")
@patch("padron.services.pipeline.gx_query.obtener_padron_vigente")
class PipelineAltasBajasDetalleTests(TestCase):
    """El panel necesita saber no solo CUANTAS altas/bajas hubo sino QUIENES
    (dni, credencial, nombre y apellido) para el popup del dashboard. Ver
    pipeline.ejecutar_actualizacion: altas sale del snapshot de la corrida
    actual, bajas sale del snapshot GUARDADO en la corrida anterior."""

    def test_primera_corrida_no_tiene_con_que_comparar(self, mock_gx, mock_subir, mock_ultimo):
        _mockear_misrx(mock_subir, mock_ultimo)
        mock_gx.return_value = CORRIDA_1

        run = ejecutar_actualizacion(trigger=PadronRun.TRIGGER_MANUAL)

        self.assertEqual(run.estado, PadronRun.ESTADO_OK)
        self.assertIsNone(run.altas_count)
        self.assertIsNone(run.bajas_count)
        self.assertEqual(run.altas_detalle, [])
        self.assertEqual(run.bajas_detalle, [])
        self.assertEqual(len(run.registros_incluidos), 2)

    def test_segunda_corrida_detalla_quien_entro_y_quien_salio(self, mock_gx, mock_subir, mock_ultimo):
        _mockear_misrx(mock_subir, mock_ultimo)

        mock_gx.return_value = CORRIDA_1
        ejecutar_actualizacion(trigger=PadronRun.TRIGGER_MANUAL)

        mock_gx.return_value = CORRIDA_2
        run2 = ejecutar_actualizacion(trigger=PadronRun.TRIGGER_MANUAL)

        self.assertEqual(run2.altas_count, 1)
        self.assertEqual(run2.bajas_count, 1)

        self.assertEqual(len(run2.altas_detalle), 1)
        self.assertEqual(run2.altas_detalle[0]["dni"], "333")
        self.assertEqual(run2.altas_detalle[0]["nombres"], "Marta")
        self.assertEqual(run2.altas_detalle[0]["apellido"], "Diaz")
        self.assertEqual(run2.altas_detalle[0]["nro_afiliado"], "1003")

        self.assertEqual(len(run2.bajas_detalle), 1)
        self.assertEqual(run2.bajas_detalle[0]["dni"], "222")
        self.assertEqual(run2.bajas_detalle[0]["nombres"], "Luis")
        self.assertEqual(run2.bajas_detalle[0]["apellido"], "Gomez")
        self.assertEqual(run2.bajas_detalle[0]["nro_afiliado"], "1002")

    def test_baja_sin_snapshot_previo_degrada_sin_romper(self, mock_gx, mock_subir, mock_ultimo):
        """Una corrida de antes de este campo (registros_incluidos vacio, como
        quedaron todas las corridas historicas) no tiene de donde sacar el
        nombre de una baja - debe quedar detalle vacio, sin romper el pipeline."""
        _mockear_misrx(mock_subir, mock_ultimo)

        PadronRun.objects.create(
            disparado_por=PadronRun.TRIGGER_AUTOMATICO,
            estado=PadronRun.ESTADO_OK,
            dnis_incluidos=["111", "222"],
            registros_incluidos=[],
            total_enviado_misrx=2,
        )

        mock_gx.return_value = [FILA_ANA]  # Luis (222) se da de baja
        run = ejecutar_actualizacion(trigger=PadronRun.TRIGGER_MANUAL)

        self.assertEqual(run.bajas_count, 1)
        self.assertEqual(run.bajas_detalle, [])
