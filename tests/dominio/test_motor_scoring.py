"""Tests del motor de scoring (agnóstico, puro)."""

from decimal import Decimal

from backend.dominio.motor_scoring import _normalizar, calcular_score
from backend.modelos.enumeraciones import CalidadDato

D = Decimal


def test_calculo_completo():
    # pesos a=0.5 b=0.3 c=0.2 ; normalizados a=100 b=50 c=0
    # score_bruto = 100×0.5 + 50×0.3 + 0×0.2 = 65
    r = calcular_score(
        componentes_crudos={"a": D("1.0"), "b": D("0.5"), "c": D("0.0")},
        pesos={"a": 0.5, "b": 0.3, "c": 0.2},
        normalizacion={
            "a": {"min": 0, "max": 1, "direccion": "asc"},
            "b": {"min": 0, "max": 1, "direccion": "asc"},
            "c": {"min": 0, "max": 1, "direccion": "asc"},
        },
        riesgo_pais=D("0"),
    )
    assert r.estado_calidad == CalidadDato.COMPLETO
    assert r.score_bruto == D("65")
    assert r.score_total == D("65")


def test_redistribucion_ante_componente_no_calculable():
    # c ausente (None) → PARCIAL; peso 0.2 se redistribuye entre a y b.
    # peso_disponible = 0.8 ; efectivos a=0.625 b=0.375
    # score = 100×0.625 + 50×0.375 = 62.5 + 18.75 = 81.25
    r = calcular_score(
        componentes_crudos={"a": D("1.0"), "b": D("0.5"), "c": None},
        pesos={"a": 0.5, "b": 0.3, "c": 0.2},
        normalizacion={},  # curvas por defecto min0 max1 asc
        riesgo_pais=D("0"),
    )
    assert r.estado_calidad == CalidadDato.PARCIAL
    assert r.score_bruto == D("81.25")
    assert r.desglose["componentes"]["c"]["calculable"] is False
    assert r.desglose["hubo_redistribucion"] is True


def test_riesgo_pais_es_multiplicador():
    # score_total = score_bruto × (1 − 0.25) = 65 × 0.75 = 48.75
    r = calcular_score(
        componentes_crudos={"a": D("1.0"), "b": D("0.5"), "c": D("0.0")},
        pesos={"a": 0.5, "b": 0.3, "c": 0.2},
        normalizacion={},
        riesgo_pais=D("0.25"),
    )
    assert r.score_bruto == D("65")
    assert r.score_total == D("48.75")


def test_no_calculable_todos_ausentes():
    r = calcular_score(
        componentes_crudos={"a": None, "b": None},
        pesos={"a": 0.5, "b": 0.5},
        normalizacion={},
        riesgo_pais=D("0"),
    )
    assert r.estado_calidad == CalidadDato.NO_CALCULABLE
    assert r.score_bruto is None
    assert r.score_total is None


def test_normalizacion_clamp_y_direccion():
    # asc, satura por encima del máximo
    assert _normalizar(D("0.14"), {"min": 0, "max": 0.07, "direccion": "asc"}) == D("100")
    assert _normalizar(D("0.035"), {"min": 0, "max": 0.07, "direccion": "asc"}) == D("50")
    # penalización de riesgo_activo: 0 → 100, −100 → 0 (asc, min −100 max 0)
    assert _normalizar(D("0"), {"min": -100, "max": 0, "direccion": "asc"}) == D("100")
    assert _normalizar(D("-50"), {"min": -100, "max": 0, "direccion": "asc"}) == D("50")


def test_determinismo():
    args = dict(
        componentes_crudos={"a": D("0.8"), "b": D("0.3")},
        pesos={"a": 0.6, "b": 0.4},
        normalizacion={},
        riesgo_pais=D("0.12"),
    )
    r1 = calcular_score(**args)
    r2 = calcular_score(**args)
    assert r1.score_bruto == r2.score_bruto
    assert r1.score_total == r2.score_total
    assert r1.desglose == r2.desglose


def test_desglose_lleva_contribucion_por_componente():
    r = calcular_score(
        componentes_crudos={"a": D("1.0"), "b": D("0.0")},
        pesos={"a": 0.7, "b": 0.3},
        normalizacion={},
        riesgo_pais=D("0"),
    )
    # a normalizado 100, contribucion 100×0.7 = 70 ; score = 70
    assert D(r.desglose["componentes"]["a"]["contribucion"]) == D("70")
    assert r.score_bruto == D("70")
