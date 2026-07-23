"""Motor financiero determinista.

PRINCIPIO 1: Python calcula, Claude interpreta. Todos los cálculos financieros
viven aquí, en una FUNCIÓN PURA: mismos inputs → mismo output, siempre. Sin I/O,
sin red, sin fecha del sistema, sin acceso a configuración.

PRINCIPIO 2: ninguna constante de negocio (peso, umbral, coste, tipo) vive aquí.
Todo entra por argumentos. Este módulo no conoce ningún valor de negocio.

MULTI-DIVISA (crítico para DO/VE): antes de cualquier operación, el motor
normaliza TODOS los inputs monetarios (precio, coste de reforma, gastos,
benchmarks) a una única `moneda_calculo`. La conversión es aritmética Python; las
TASAS entran como datos (`tasas`), leídas por el servicio de la tabla tipos_cambio
— nunca las inventa Claude, nunca están hardcodeadas. Si falta una sola tasa
necesaria para completar la normalización → el inmueble sale NO_CALCULABLE,
nombrando el par de divisas que falta. Jamás una tasa asumida.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from ..modelos.enumeraciones import CalidadDato

VERSION_MOTOR = "motor-financiero-1.2.0"  # 1.2.0: exención de gastos (CONFOTUR)

_CERO = Decimal(0)
_UNO = Decimal(1)
_MESES_ANIO = Decimal(12)


@dataclass(frozen=True)
class GastoAdquisicionEntrada:
    """Un gasto de adquisición. `tipo` = 'PORCENTAJE' o 'FIJO'. `valor` None = ausente.

    `moneda` solo importa para FIJO (importe absoluto). PORCENTAJE se aplica al
    precio (ya en moneda de cálculo), así que es agnóstico a divisa.

    `exento_confotur` viene de la configuración, no de aquí: el motor no sabe qué
    es un impuesto de transferencia ni qué es CONFOTUR. Solo sabe que hay gastos
    marcados como exentos y que, si el inmueble está acogido, no se suman.
    """

    concepto: str
    tipo: str
    valor: Decimal | None
    moneda: str | None = None
    exento_confotur: bool = False


@dataclass(frozen=True)
class EntradaFinanciera:
    """Todo lo que el motor necesita. Los None son datos ausentes (nunca inventados)."""

    precio: Decimal | None
    superficie_util_m2: Decimal | None
    superficie_construida_m2: Decimal | None
    gastos_comunidad_mes: Decimal | None
    nivel_reforma: str  # NINGUNA | COSMETICA | MEDIA | INTEGRAL | DESCONOCIDO
    coste_reforma_m2: Decimal | None      # de costes_reforma; None = pendiente
    gastos_adquisicion: list[GastoAdquisicionEntrada]
    precio_m2_alquiler_medio: Decimal | None  # benchmark; None = pendiente
    precio_m2_venta_medio: Decimal | None     # benchmark; None = pendiente
    # Supuestos e mercado (ya resueltos: ltv efectivo tras tope de país)
    ltv: Decimal
    tipo_interes_anual: Decimal | None    # None = pendiente (p.ej. DO)
    plazo_anos: int
    vacancia_pct: Decimal
    gastos_gestion_pct: Decimal
    # --- Multi-divisa ---
    # Moneda en la que se calcula todo (= moneda del anuncio). Precio y gastos de
    # comunidad ya están en esta moneda.
    moneda_calculo: str | None = None
    moneda_coste_reforma: str | None = None   # moneda del €/m² de reforma
    moneda_benchmark: str | None = None       # moneda de los precios/m² de zona
    # Mapa de tasas (origen, destino) -> tasa. Lo provee el servicio desde BD.
    tasas: dict[tuple[str, str], Decimal] = field(default_factory=dict)
    # --- Exención fiscal (CONFOTUR en RD, pero el motor no conoce el nombre) ---
    # None = DESCONOCIDO. No es False: si hay gastos marcados como exentos y no
    # sabemos si el inmueble está acogido, el coste calculado puede estar inflado,
    # y eso degrada la calidad del dato en vez de pasar desapercibido.
    tiene_confotur: bool | None = None


@dataclass(frozen=True)
class ResultadoFinanciero:
    metricas: dict[str, Decimal] = field(default_factory=dict)
    inputs_auditoria: dict[str, dict] = field(default_factory=dict)
    estado_calidad: CalidadDato = CalidadDato.NO_CALCULABLE
    campos_faltantes: list[str] = field(default_factory=list)
    version_motor: str = VERSION_MOTOR


def _convertir(
    monto: Decimal | None, origen: str | None, destino: str | None,
    tasas: dict[tuple[str, str], Decimal],
) -> tuple[Decimal | None, str | None]:
    """Convierte `monto` de `origen` a `destino`.

    Devuelve (valor_convertido | None, par_faltante | None):
    - monto None → (None, None): nada que convertir (dato ausente).
    - misma moneda / sin especificar → (monto, None): sin conversión.
    - tasa disponible → (monto*tasa, None).
    - tasa AUSENTE → (None, "ORIGEN->DESTINO"): normalización imposible.
    """
    if monto is None:
        return None, None
    if not destino or not origen or origen == destino:
        return monto, None
    tasa = tasas.get((origen, destino))
    if tasa is None:
        return None, f"{origen}->{destino}"
    return monto * tasa, None


def _cuota_hipoteca_anual(prestamo: Decimal, tipo_anual: Decimal, plazo_anos: int) -> Decimal:
    """Cuota anual por amortización francesa. Exponente entero → determinista."""
    if prestamo <= _CERO:
        return _CERO
    n = plazo_anos * 12
    if n <= 0:
        return _CERO
    if tipo_anual == _CERO:
        return prestamo / Decimal(n) * _MESES_ANIO
    i = tipo_anual / _MESES_ANIO
    factor = (_UNO + i) ** n            # exponente entero
    cuota_mensual = prestamo * i * factor / (factor - _UNO)
    return cuota_mensual * _MESES_ANIO


def calcular_metricas(e: EntradaFinanciera) -> ResultadoFinanciero:
    """Calcula todas las métricas financieras en la moneda de cálculo.

    Estado de calidad:
    - NO_CALCULABLE: falta un dato crítico (precio o superficie) O falta una tasa
      de cambio necesaria para normalizar un input presente en otra divisa.
    - PARCIAL: se calculó lo posible; faltan datos de configuración (redistribuye).
    - COMPLETO: todas las métricas calculadas.
    """
    metricas: dict[str, Decimal] = {}
    auditoria: dict[str, dict] = {}
    faltantes: list[str] = []

    superficie = e.superficie_util_m2 or e.superficie_construida_m2

    # --- Datos críticos ------------------------------------------------------
    if e.precio is None or superficie is None or superficie == _CERO:
        criticos = []
        if e.precio is None:
            criticos.append("precio")
        if superficie is None or superficie == _CERO:
            criticos.append("superficie")
        return ResultadoFinanciero(
            estado_calidad=CalidadDato.NO_CALCULABLE, campos_faltantes=criticos
        )

    precio = e.precio

    # --- Normalización de divisa (antes de cualquier operación) --------------
    # Precio y gastos de comunidad ya están en moneda_calculo (vienen del anuncio).
    faltan_tasas: list[str] = []

    def _norm(monto, origen):
        valor, par = _convertir(monto, origen, e.moneda_calculo, e.tasas)
        if par:
            faltan_tasas.append(par)
        return valor

    coste_m2_norm = _norm(e.coste_reforma_m2, e.moneda_coste_reforma)
    alquiler_norm = _norm(e.precio_m2_alquiler_medio, e.moneda_benchmark)
    venta_norm = _norm(e.precio_m2_venta_medio, e.moneda_benchmark)
    gastos_norm: list[GastoAdquisicionEntrada] = []
    for g in e.gastos_adquisicion:
        if g.tipo == "FIJO":
            gastos_norm.append(
                GastoAdquisicionEntrada(
                    g.concepto, g.tipo, _norm(g.valor, g.moneda), e.moneda_calculo,
                    g.exento_confotur,
                )
            )
        else:  # PORCENTAJE: agnóstico a divisa
            gastos_norm.append(g)

    if faltan_tasas:
        # Falta una tasa para completar la normalización → NO_CALCULABLE.
        return ResultadoFinanciero(
            estado_calidad=CalidadDato.NO_CALCULABLE,
            campos_faltantes=[f"tipo_cambio[{p}]" for p in sorted(set(faltan_tasas))],
        )

    def registrar(nombre: str, valor: Decimal, formula: str, inputs: dict) -> None:
        metricas[nombre] = valor
        auditoria[nombre] = {"valor": str(valor), "formula": formula, "inputs": inputs}

    auditoria["_moneda_calculo"] = {"valor": e.moneda_calculo or "(única)", "formula": "moneda de cálculo", "inputs": {}}

    # --- Coste de reforma ----------------------------------------------------
    coste_reforma: Decimal | None
    if e.nivel_reforma == "NINGUNA":
        coste_reforma = _CERO
        registrar("coste_reforma", _CERO, "nivel NINGUNA → 0", {"nivel": "NINGUNA"})
    elif coste_m2_norm is None:
        coste_reforma = None
        faltantes.append(f"coste_reforma[{e.nivel_reforma}]")
    else:
        coste_reforma = coste_m2_norm * superficie
        registrar(
            "coste_reforma", coste_reforma, "coste_m2(norm) × superficie",
            {"coste_m2": str(coste_m2_norm), "superficie_m2": str(superficie)},
        )

    # --- Gastos de adquisición ----------------------------------------------
    gastos_total: Decimal | None = _CERO
    detalle_gastos = {}
    # ¿Hay algún concepto que una exención podría eximir? Es lo que decide si el
    # desconocimiento importa: sin conceptos exentos configurados, da igual.
    hay_exenciones = any(g.exento_confotur for g in gastos_norm)
    exento = e.tiene_confotur is True
    for g in gastos_norm:
        if g.exento_confotur and exento:
            # Acogido a la exención: este concepto no se paga. Se deja constancia
            # en la auditoría (0 explícito) en vez de desaparecer de la cuenta.
            detalle_gastos[g.concepto] = "0 (exento)"
            continue
        if g.valor is None:
            faltantes.append(f"gasto_adquisicion[{g.concepto}]")
            gastos_total = None
            continue
        importe = g.valor * precio if g.tipo == "PORCENTAJE" else g.valor
        detalle_gastos[g.concepto] = str(importe)
        if gastos_total is not None:
            gastos_total = gastos_total + importe
    if not gastos_norm:
        gastos_total = None
        faltantes.append("gastos_adquisicion[sin_configurar]")
    # Desconocido NO es "no tiene": el total se calcula aplicando el gasto (la
    # hipótesis conservadora, la que no infla el ROI), pero el inmueble no puede
    # presentarse como COMPLETO mientras no se confirme.
    if hay_exenciones and e.tiene_confotur is None:
        faltantes.append("tiene_confotur[desconocido]")
    if gastos_total is not None:
        registrar(
            "gastos_adquisicion_total", gastos_total, "Σ gastos (% × precio | fijo)",
            detalle_gastos,
        )

    # --- Coste total e inversión --------------------------------------------
    if gastos_total is not None:
        coste_total = precio + gastos_total
        registrar(
            "coste_total_adquisicion", coste_total, "precio + gastos_adquisicion",
            {"precio": str(precio), "gastos": str(gastos_total)},
        )
    else:
        coste_total = None

    if coste_total is not None and coste_reforma is not None:
        inversion_total = coste_total + coste_reforma
        registrar(
            "inversion_total", inversion_total, "coste_total + coste_reforma",
            {"coste_total": str(coste_total), "coste_reforma": str(coste_reforma)},
        )
    else:
        inversion_total = None

    # --- Financiación --------------------------------------------------------
    prestamo = precio * e.ltv
    entrada = precio - prestamo
    registrar("prestamo", prestamo, "precio × ltv", {"precio": str(precio), "ltv": str(e.ltv)})
    registrar("entrada", entrada, "precio − prestamo", {"precio": str(precio), "prestamo": str(prestamo)})

    cuota_anual: Decimal | None
    if prestamo == _CERO:
        cuota_anual = _CERO
        registrar("cuota_hipoteca_anual", _CERO, "sin financiación (ltv=0)", {})
    elif e.tipo_interes_anual is None:
        cuota_anual = None
        faltantes.append("tipo_interes_anual")
    else:
        cuota_anual = _cuota_hipoteca_anual(prestamo, e.tipo_interes_anual, e.plazo_anos)
        registrar(
            "cuota_hipoteca_anual", cuota_anual, "amortización francesa",
            {"prestamo": str(prestamo), "tipo_anual": str(e.tipo_interes_anual),
             "plazo_anos": e.plazo_anos},
        )

    if inversion_total is not None:
        capital_invertido = entrada + (gastos_total or _CERO) + (coste_reforma or _CERO)
        registrar(
            "capital_invertido", capital_invertido, "entrada + gastos + reforma",
            {"entrada": str(entrada), "gastos": str(gastos_total),
             "reforma": str(coste_reforma)},
        )
    else:
        capital_invertido = None

    # --- Ingresos por alquiler ----------------------------------------------
    renta_neta: Decimal | None = None
    if alquiler_norm is None:
        faltantes.append("benchmark_alquiler")
    else:
        renta_bruta = alquiler_norm * superficie * _MESES_ANIO
        registrar(
            "renta_anual_bruta", renta_bruta, "alquiler_m2(norm) × superficie × 12",
            {"alquiler_m2": str(alquiler_norm), "superficie": str(superficie)},
        )
        rentabilidad_bruta = renta_bruta / precio
        registrar(
            "rentabilidad_bruta", rentabilidad_bruta, "renta_anual_bruta / precio",
            {"renta_anual_bruta": str(renta_bruta), "precio": str(precio)},
        )
        renta_efectiva = renta_bruta * (_UNO - e.vacancia_pct)
        comunidad_anual = (e.gastos_comunidad_mes or _CERO) * _MESES_ANIO
        gastos_op = renta_efectiva * e.gastos_gestion_pct + comunidad_anual
        renta_neta = renta_efectiva - gastos_op
        registrar(
            "renta_neta_operativa", renta_neta,
            "renta_bruta×(1−vacancia) − gestión − comunidad",
            {"renta_bruta": str(renta_bruta), "vacancia_pct": str(e.vacancia_pct),
             "gastos_gestion_pct": str(e.gastos_gestion_pct),
             "comunidad_anual": str(comunidad_anual)},
        )
        cap_rate = renta_neta / precio
        registrar("cap_rate", cap_rate, "renta_neta_operativa / precio",
                  {"renta_neta": str(renta_neta), "precio": str(precio)})

    # --- Flujo de caja y rentabilidad neta ----------------------------------
    if renta_neta is not None and cuota_anual is not None:
        flujo = renta_neta - cuota_anual
        registrar("flujo_caja_anual", flujo, "renta_neta_operativa − cuota_anual",
                  {"renta_neta": str(renta_neta), "cuota_anual": str(cuota_anual)})
        if capital_invertido is not None and capital_invertido != _CERO:
            roi = flujo / capital_invertido
            registrar("roi_neto", roi, "flujo_caja_anual / capital_invertido",
                      {"flujo": str(flujo), "capital_invertido": str(capital_invertido)})

    # --- Descuento sobre mercado --------------------------------------------
    if venta_norm is None or venta_norm == _CERO:
        faltantes.append("benchmark_venta")
    else:
        precio_m2 = precio / superficie
        descuento = _UNO - (precio_m2 / venta_norm)
        registrar(
            "descuento_mercado", descuento, "1 − (precio/m² / precio/m² medio zona)",
            {"precio_m2": str(precio_m2), "precio_m2_medio": str(venta_norm)},
        )

    estado = CalidadDato.COMPLETO if not faltantes else CalidadDato.PARCIAL
    return ResultadoFinanciero(
        metricas=metricas, inputs_auditoria=auditoria,
        estado_calidad=estado, campos_faltantes=faltantes,
    )
