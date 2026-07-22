"""Blindaje: un score con señales ignoradas nunca se presenta como COMPLETO.

El peligro no es que falte el catálogo — eso es config, y se ve en "Estado por país".
El peligro es que el scoring SIGUE puntuando sin él, y el fallo empuja al alza:
`riesgo_activo` sin penalizaciones puntúa como "sin riesgo alguno" (máximo). Un piso
con OKUPAS en un país sin catálogo entraría al ranking con buena nota y estado
COMPLETO. Estos tests fijan que eso no puede pasar.
"""

from backend.modelos.enumeraciones import CalidadDato
from backend.servicios.calculo_scoring import ajustar_por_senales_ignoradas


def test_completo_con_senales_ignoradas_baja_a_parcial():
    """El caso que engaña: score limpio sobre un riesgo que nunca se evaluó."""
    estado, desglose = ajustar_por_senales_ignoradas(
        CalidadDato.COMPLETO, {"componentes": {}}, ["OKUPAS", "CARGAS"]
    )
    assert estado == CalidadDato.PARCIAL, "un riesgo no evaluado no puede salir COMPLETO"
    assert desglose["senales_no_reconocidas"] == ["OKUPAS", "CARGAS"]


def test_sin_senales_ignoradas_no_toca_nada():
    original = {"componentes": {"roi": 1}}
    estado, desglose = ajustar_por_senales_ignoradas(CalidadDato.COMPLETO, original, [])
    assert estado == CalidadDato.COMPLETO
    assert desglose == original
    assert "senales_no_reconocidas" not in desglose


def test_parcial_sigue_parcial_pero_registra_el_motivo():
    estado, desglose = ajustar_por_senales_ignoradas(
        CalidadDato.PARCIAL, {}, ["HUMEDADES_ESTRUCTURALES"]
    )
    assert estado == CalidadDato.PARCIAL
    assert desglose["senales_no_reconocidas"] == ["HUMEDADES_ESTRUCTURALES"]


def test_descartado_por_riesgo_no_se_ablanda():
    """Un eliminatorio manda: no se degrada a PARCIAL por tener señales sueltas."""
    estado, desglose = ajustar_por_senales_ignoradas(
        CalidadDato.DESCARTADO_RIESGO, {"descartado_por": ["OKUPAS"]}, ["CODIGO_RARO"]
    )
    assert estado == CalidadDato.DESCARTADO_RIESGO
    assert desglose["descartado_por"] == ["OKUPAS"]
    assert desglose["senales_no_reconocidas"] == ["CODIGO_RARO"]


def test_no_calculable_no_se_ablanda():
    estado, _ = ajustar_por_senales_ignoradas(CalidadDato.NO_CALCULABLE, {}, ["X"])
    assert estado == CalidadDato.NO_CALCULABLE


def test_no_muta_el_desglose_de_entrada():
    """Función pura: el dict que entra no se toca."""
    original = {"componentes": {}}
    _, nuevo = ajustar_por_senales_ignoradas(CalidadDato.COMPLETO, original, ["X"])
    assert "senales_no_reconocidas" not in original
    assert nuevo is not original
