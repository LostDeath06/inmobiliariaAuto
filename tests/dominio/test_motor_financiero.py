"""Tests del motor financiero con casos calculados a mano.

Es la pieza que no puede fallar (Principio 1). Todos los valores esperados están
calculados a mano en los comentarios.
"""

from decimal import Decimal

import pytest

from backend.dominio.motor_financiero import (
    EntradaFinanciera,
    GastoAdquisicionEntrada,
    _cuota_hipoteca_anual,
    calcular_metricas,
)
from backend.modelos.enumeraciones import CalidadDato

D = Decimal


def _entrada_base(**cambios):
    base = dict(
        precio=D("100000"),
        superficie_util_m2=D("80"),
        superficie_construida_m2=D("90"),
        gastos_comunidad_mes=D("50"),
        nivel_reforma="MEDIA",
        coste_reforma_m2=D("300"),
        gastos_adquisicion=[
            GastoAdquisicionEntrada("ITP", "PORCENTAJE", D("0.10")),
            GastoAdquisicionEntrada("NOTARIA", "FIJO", D("1200")),
        ],
        precio_m2_alquiler_medio=D("10"),
        precio_m2_venta_medio=D("1500"),
        ltv=D("0"),          # al contado (caso VE) → sin transcendentales
        tipo_interes_anual=D("0.035"),
        plazo_anos=25,
        vacancia_pct=D("0.05"),
        gastos_gestion_pct=D("0.08"),
    )
    base.update(cambios)
    return EntradaFinanciera(**base)


def test_caso_completo_al_contado():
    """Caso COMPLETO, ltv=0 (todo a mano, sin amortización con interés).

    superficie útil = 80 m²
    coste_reforma = 300 × 80 = 24 000
    gastos_adquisicion = 0.10×100000 (ITP) + 1200 (notaría) = 11 200
    coste_total = 100000 + 11200 = 111 200
    inversion_total = 111200 + 24000 = 135 200
    prestamo = 100000 × 0 = 0 ; entrada = 100 000 ; cuota = 0
    capital_invertido = 100000 + 11200 + 24000 = 135 200
    renta_bruta = 10 × 80 × 12 = 9 600
    renta_efectiva = 9600 × 0.95 = 9 120
    gastos_op = 9120 × 0.08 + 50×12 = 729.6 + 600 = 1 329.6
    renta_neta = 9120 − 1329.6 = 7 790.4
    cap_rate = 7790.4 / 100000 = 0.077904
    flujo = 7790.4 − 0 = 7 790.4
    roi_neto = 7790.4 / 135200 = 0.0576213…  → 0.057621
    descuento = 1 − (1250/1500) = 0.166666…  → 0.166667
    """
    r = calcular_metricas(_entrada_base())
    assert r.estado_calidad == CalidadDato.COMPLETO
    assert r.campos_faltantes == []
    m = r.metricas
    assert m["coste_reforma"] == D("24000")
    assert m["gastos_adquisicion_total"] == D("11200")
    assert m["coste_total_adquisicion"] == D("111200")
    assert m["inversion_total"] == D("135200")
    assert m["prestamo"] == D("0")
    assert m["entrada"] == D("100000")
    assert m["cuota_hipoteca_anual"] == D("0")
    assert m["capital_invertido"] == D("135200")
    assert m["renta_anual_bruta"] == D("9600")
    assert m["rentabilidad_bruta"] == D("0.096")
    assert m["renta_neta_operativa"] == D("7790.4")
    assert m["cap_rate"] == D("0.077904")
    assert m["flujo_caja_anual"] == D("7790.4")
    assert m["roi_neto"].quantize(D("0.000001")) == D("0.057621")
    assert m["descuento_mercado"].quantize(D("0.000001")) == D("0.166667")


def test_amortizacion_sin_interes_es_exacta():
    # prestamo 60 000, tipo 0, plazo 10 años (120 meses) → cuota anual = 60000/120*12 = 6000
    assert _cuota_hipoteca_anual(D("60000"), D("0"), 10) == D("6000")


def test_amortizacion_valor_de_libro():
    # 100 000 al 5% anual a 30 años → cuota mensual ≈ 536.82 (valor de manual)
    cuota_anual = _cuota_hipoteca_anual(D("100000"), D("0.05"), 30)
    cuota_mensual = (cuota_anual / 12).quantize(D("0.01"))
    assert cuota_mensual == D("536.82")


def test_financiado_flujo_es_renta_menos_cuota():
    r = calcular_metricas(_entrada_base(ltv=D("0.70")))
    m = r.metricas
    # prestamo = 70 000, entrada = 30 000
    assert m["prestamo"] == D("70000")
    assert m["entrada"] == D("30000")
    # cuota > 0 y flujo = renta_neta − cuota
    assert m["cuota_hipoteca_anual"] > 0
    assert m["flujo_caja_anual"] == m["renta_neta_operativa"] - m["cuota_hipoteca_anual"]
    # capital_invertido = 30000 + 11200 + 24000 = 65 200
    assert m["capital_invertido"] == D("65200")


def test_no_calculable_sin_precio():
    r = calcular_metricas(_entrada_base(precio=None))
    assert r.estado_calidad == CalidadDato.NO_CALCULABLE
    assert "precio" in r.campos_faltantes
    assert r.metricas == {}


def test_no_calculable_sin_superficie():
    r = calcular_metricas(
        _entrada_base(superficie_util_m2=None, superficie_construida_m2=None)
    )
    assert r.estado_calidad == CalidadDato.NO_CALCULABLE
    assert "superficie" in r.campos_faltantes


def test_parcial_sin_benchmark_alquiler():
    r = calcular_metricas(_entrada_base(precio_m2_alquiler_medio=None))
    assert r.estado_calidad == CalidadDato.PARCIAL
    assert "benchmark_alquiler" in r.campos_faltantes
    # Lo que no depende del alquiler sí se calcula.
    assert r.metricas["inversion_total"] == D("135200")
    # roi_neto y cap_rate NO están (dependen del alquiler).
    assert "roi_neto" not in r.metricas
    assert "cap_rate" not in r.metricas


def test_parcial_sin_coste_reforma():
    r = calcular_metricas(_entrada_base(coste_reforma_m2=None))
    assert r.estado_calidad == CalidadDato.PARCIAL
    assert any("coste_reforma" in c for c in r.campos_faltantes)
    # Sin reforma no hay inversion_total ni roi_neto, pero sí cap_rate (sobre precio).
    assert "inversion_total" not in r.metricas
    assert "cap_rate" in r.metricas


def test_parcial_sin_gastos_configurados():
    r = calcular_metricas(_entrada_base(gastos_adquisicion=[]))
    assert r.estado_calidad == CalidadDato.PARCIAL
    assert "gastos_adquisicion[sin_configurar]" in r.campos_faltantes


def test_nivel_ninguna_reforma_cero():
    r = calcular_metricas(_entrada_base(nivel_reforma="NINGUNA", coste_reforma_m2=None))
    # NINGUNA → coste 0 aunque no haya coste_m2 (no es dato faltante).
    assert r.metricas["coste_reforma"] == D("0")
    assert not any("coste_reforma" in c for c in r.campos_faltantes)


def test_determinismo():
    e = _entrada_base(ltv=D("0.70"))
    r1 = calcular_metricas(e)
    r2 = calcular_metricas(e)
    assert r1.metricas == r2.metricas
    assert r1.inputs_auditoria == r2.inputs_auditoria


def test_auditoria_lleva_formula_e_inputs():
    r = calcular_metricas(_entrada_base())
    aud = r.inputs_auditoria["coste_reforma"]
    assert "formula" in aud and "inputs" in aud and "valor" in aud


# ---------------------------------------------------------------------------
#  Multi-divisa (crítico para RD y VE): normalización con tipos_cambio.
# ---------------------------------------------------------------------------


def _entrada_usd_con_benchmark_dop(tasas):
    """Anuncio en USD, benchmark en DOP. Con tasa DOP→USD=0.02 los números deben
    coincidir EXACTAMENTE con el caso al contado en EUR (500 DOP/m² × 0.02 = 10)."""
    return EntradaFinanciera(
        precio=D("100000"),
        superficie_util_m2=D("80"),
        superficie_construida_m2=D("90"),
        gastos_comunidad_mes=D("50"),
        nivel_reforma="MEDIA",
        coste_reforma_m2=D("300"),          # en USD (misma que cálculo)
        gastos_adquisicion=[
            GastoAdquisicionEntrada("ITP", "PORCENTAJE", D("0.10"), None),
            GastoAdquisicionEntrada("NOTARIA", "FIJO", D("1200"), "USD"),
        ],
        precio_m2_alquiler_medio=D("500"),  # en DOP
        precio_m2_venta_medio=D("75000"),   # en DOP
        ltv=D("0"),
        tipo_interes_anual=D("0.035"),
        plazo_anos=25,
        vacancia_pct=D("0.05"),
        gastos_gestion_pct=D("0.08"),
        moneda_calculo="USD",
        moneda_coste_reforma="USD",
        moneda_benchmark="DOP",
        tasas=tasas,
    )


def test_fx_usd_con_benchmark_dop_roi_correcto():
    # tasa DOP→USD = 0.02  ⇒  alquiler 500 DOP/m² = 10 USD/m² ; venta 75000 = 1500 USD
    r = calcular_metricas(_entrada_usd_con_benchmark_dop({("DOP", "USD"): D("0.02")}))
    assert r.estado_calidad == CalidadDato.COMPLETO
    m = r.metricas
    assert m["renta_anual_bruta"] == D("9600")            # 10 × 80 × 12
    assert m["renta_neta_operativa"] == D("7790.4")
    assert m["cap_rate"] == D("0.077904")
    assert m["inversion_total"] == D("135200")
    assert m["roi_neto"].quantize(D("0.000001")) == D("0.057621")
    assert m["descuento_mercado"].quantize(D("0.000001")) == D("0.166667")


def test_fx_falta_tasa_es_no_calculable_nombrando_el_par():
    # Sin la tasa DOP→USD no se puede normalizar el benchmark → NO_CALCULABLE.
    r = calcular_metricas(_entrada_usd_con_benchmark_dop({}))
    assert r.estado_calidad == CalidadDato.NO_CALCULABLE
    assert "tipo_cambio[DOP->USD]" in r.campos_faltantes
    assert r.metricas == {}                                # no rankea con basura


def test_fx_espana_todo_eur_no_cambia():
    # España (todo EUR): mismos valores con moneda_calculo=EUR y sin tasas.
    base = _entrada_base()
    ent = EntradaFinanciera(
        **{**base.__dict__, "moneda_calculo": "EUR", "moneda_coste_reforma": "EUR",
           "moneda_benchmark": "EUR", "tasas": {}}
    )
    r_eur = calcular_metricas(ent)
    r_ref = calcular_metricas(base)  # sin monedas (comportamiento previo)
    assert r_eur.estado_calidad == CalidadDato.COMPLETO
    assert r_eur.metricas == r_ref.metricas   # España no cambia
