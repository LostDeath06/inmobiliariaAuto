"""Tests de la exención de gastos de adquisición (CONFOTUR, Ley 158-01 RD).

Dos inmuebles idénticos, uno acogido a CONFOTUR y otro no, tienen gastos de
adquisición muy distintos. Aplicar el impuesto de transferencia a todos infla el
coste de los exentos y hunde su ROI: el error cae del lado que hace descartar una
inversión buena.

Lo que protegen estos tests:
1. La exención salta EXACTAMENTE los conceptos marcados, no todos.
2. `None` (desconocido) NO se trata como `False`. Nunca en silencio.
3. El motor no sabe qué es CONFOTUR: la marca viene del dato (Principio 2).
"""

from decimal import Decimal

from backend.dominio.motor_financiero import (
    EntradaFinanciera,
    GastoAdquisicionEntrada,
    calcular_metricas,
)
from backend.modelos.enumeraciones import CalidadDato

D = Decimal

# Gastos de RD: el impuesto de transferencia (3%) queda exento con CONFOTUR;
# los honorarios legales (1.25%) y el cierre (1%) se pagan igual.
_GASTOS_RD = [
    GastoAdquisicionEntrada("impuesto_transferencia", "PORCENTAJE", D("0.03"), None, True),
    GastoAdquisicionEntrada("honorarios_legales", "PORCENTAJE", D("0.0125"), None, False),
    GastoAdquisicionEntrada("gastos_cierre", "PORCENTAJE", D("0.01"), None, False),
]


def _entrada(**cambios):
    base = dict(
        precio=D("200000"),
        superficie_util_m2=D("100"),
        superficie_construida_m2=D("110"),
        gastos_comunidad_mes=None,
        nivel_reforma="NINGUNA",
        coste_reforma_m2=None,
        gastos_adquisicion=list(_GASTOS_RD),
        precio_m2_alquiler_medio=D("12"),
        precio_m2_venta_medio=D("2200"),
        ltv=D("0"),
        tipo_interes_anual=D("0.115"),
        plazo_anos=25,
        vacancia_pct=D("0.05"),
        gastos_gestion_pct=D("0.08"),
    )
    base.update(cambios)
    return EntradaFinanciera(**base)


def test_sin_confotur_paga_los_tres_gastos():
    """Confirmado que NO tiene CONFOTUR: se aplican los tres conceptos.

    200000 × (0.03 + 0.0125 + 0.01) = 200000 × 0.0525 = 10 500
    """
    r = calcular_metricas(_entrada(tiene_confotur=False))
    assert r.metricas["gastos_adquisicion_total"] == D("10500.00")
    assert r.metricas["coste_total_adquisicion"] == D("210500.00")


def test_con_confotur_exime_solo_el_impuesto_de_transferencia():
    """Acogido a CONFOTUR: no paga el 3%, pero sí el 1.25% y el 1%.

    200000 × (0.0125 + 0.01) = 200000 × 0.0225 = 4 500
    """
    r = calcular_metricas(_entrada(tiene_confotur=True))
    assert r.metricas["gastos_adquisicion_total"] == D("4500.00")
    assert r.metricas["coste_total_adquisicion"] == D("204500.00")


def test_la_exencion_queda_registrada_en_la_auditoria():
    """El concepto exento no desaparece de la cuenta: consta con importe 0."""
    r = calcular_metricas(_entrada(tiene_confotur=True))
    detalle = r.inputs_auditoria["gastos_adquisicion_total"]["inputs"]
    assert detalle["impuesto_transferencia"] == "0 (exento)"
    assert detalle["honorarios_legales"] == "2500.0000"


def test_confotur_desconocido_no_es_lo_mismo_que_no_tener():
    """`None` calcula con el impuesto aplicado (hipótesis conservadora) PERO lo dice.

    Es el caso peligroso: si `None` se tratara como `False` en silencio, un
    inmueble exento se presentaría como COMPLETO con un coste inflado y nadie
    sabría que hay una pregunta sin responder detrás del número.
    """
    r = calcular_metricas(_entrada(tiene_confotur=None))
    # Se calcula con el impuesto aplicado: no se regala una exención sin confirmar.
    assert r.metricas["gastos_adquisicion_total"] == D("10500.00")
    # Pero NO puede presentarse como COMPLETO.
    assert r.estado_calidad == CalidadDato.PARCIAL
    assert "tiene_confotur[desconocido]" in r.campos_faltantes


def test_confotur_confirmado_no_ensucia_la_calidad_del_dato():
    """Con la respuesta dada (sea true o false) no queda pregunta pendiente."""
    for valor in (True, False):
        r = calcular_metricas(_entrada(tiene_confotur=valor))
        assert "tiene_confotur[desconocido]" not in r.campos_faltantes


def test_sin_conceptos_exentos_el_desconocimiento_no_importa():
    """En un país sin exenciones configuradas (España), `None` no ensucia nada.

    La pregunta solo es relevante donde hay algo que eximir. Marcar PARCIAL a
    todos los pisos españoles por un campo que allí no aplica sería ruido.
    """
    gastos_es = [
        GastoAdquisicionEntrada("itp", "PORCENTAJE", D("0.10"), None, False),
        GastoAdquisicionEntrada("notaria", "FIJO", D("750"), None, False),
    ]
    r = calcular_metricas(_entrada(gastos_adquisicion=gastos_es, tiene_confotur=None))
    assert "tiene_confotur[desconocido]" not in r.campos_faltantes
    assert r.metricas["gastos_adquisicion_total"] == D("20750.00")


def test_la_exencion_cambia_el_roi_de_verdad():
    """El punto de todo esto: con y sin CONFOTUR el ROI NO es el mismo.

    Si este test se pone verde con los dos valores iguales, la exención no está
    llegando al cálculo y el sistema estaría mintiendo sobre la rentabilidad.
    """
    con = calcular_metricas(_entrada(tiene_confotur=True))
    sin = calcular_metricas(_entrada(tiene_confotur=False))
    assert con.metricas["roi_neto"] > sin.metricas["roi_neto"]
    # La diferencia es exactamente el 3% del precio en capital invertido.
    assert (sin.metricas["capital_invertido"] - con.metricas["capital_invertido"]) == D("6000.00")


def test_el_motor_no_conoce_la_palabra_confotur_en_sus_conceptos():
    """El motor salta los gastos MARCADOS, no los que se llamen de cierta manera.

    Verificación del Principio 2: si algún día alguien mete una condición del tipo
    `if concepto == "impuesto_transferencia"`, este test lo caza.
    """
    gastos_raros = [
        GastoAdquisicionEntrada("un_concepto_cualquiera", "PORCENTAJE", D("0.05"), None, True),
        GastoAdquisicionEntrada("impuesto_transferencia", "PORCENTAJE", D("0.03"), None, False),
    ]
    r = calcular_metricas(_entrada(gastos_adquisicion=gastos_raros, tiene_confotur=True))
    # Se exime el marcado (5%) y se cobra el que NO lo está, aunque se llame
    # "impuesto_transferencia": 200000 × 0.03 = 6000.
    assert r.metricas["gastos_adquisicion_total"] == D("6000.00")


def test_gasto_fijo_tambien_puede_quedar_exento():
    """La exención no es solo para porcentajes (el IPI podría cargarse como fijo)."""
    gastos = [
        GastoAdquisicionEntrada("tasa_fija", "FIJO", D("3000"), "USD", True),
        GastoAdquisicionEntrada("cierre", "PORCENTAJE", D("0.01"), None, False),
    ]
    r = calcular_metricas(
        _entrada(gastos_adquisicion=gastos, tiene_confotur=True, moneda_calculo="USD")
    )
    assert r.metricas["gastos_adquisicion_total"] == D("2000.00")
