"""Servicio de cálculo financiero.

Orquesta: reúne los datos (inmueble, análisis, configuración de mercado del país,
costes de reforma, gastos de adquisición, benchmarks), construye la entrada del
motor financiero (función pura), calcula y persiste las métricas en moneda nativa
y convertidas a la moneda de referencia.

Nota multi-perfil: la financiación (ltv, plazo, vacancia, gestión) depende del
perfil. Se persiste una fila de métricas "canónica" por inmueble usando el perfil
predeterminado (para la ficha de detalle); el scoring recalcula las métricas
dependientes del perfil en memoria para cada perfil.

TODO(FX): se asume que costes/gastos/benchmarks están en la misma moneda que el
inmueble (config por país). Si difieren, habría que convertir con tipos_cambio.
"""

from __future__ import annotations

from decimal import Decimal

from ..dominio import motor_financiero as mf
from ..modelos.analisis import AnalisisCualitativo
from ..modelos.configuracion import PerfilInversor
from ..modelos.enumeraciones import CalidadDato
from ..modelos.pipeline import Inmueble
from ..repositorios import config_mercado, configuracion_pais, metricas as repo_metricas
from . import conversion


async def construir_entrada(
    inmueble: Inmueble,
    analisis: AnalisisCualitativo | None,
    perfil: PerfilInversor,
) -> tuple[mf.EntradaFinanciera, dict]:
    """Construye la entrada del motor y un snapshot de mercado usado."""
    pais = inmueble.pais or ""
    nivel = analisis.nivel_reforma_estimado.value if analisis else "DESCONOCIDO"

    config_pais = await configuracion_pais.obtener_config_mercado(pais)
    supuestos = perfil.supuestos or {}
    ltv_perfil = Decimal(str(supuestos.get("ltv", 0)))
    ltv_max = config_pais.ltv_max if config_pais else None
    ltv_efectivo = min(ltv_perfil, ltv_max) if ltv_max is not None else ltv_perfil
    tipo_interes = config_pais.tipo_interes_anual if config_pais else None

    coste = await config_mercado.obtener_coste_reforma(
        pais, analisis.nivel_reforma_estimado
    ) if analisis else None
    coste_m2 = coste.coste_m2 if coste else None
    moneda_coste = coste.moneda if coste else None

    # --- Gastos de adquisición: genéricos + los de la región del inmueble ------
    # El ITP español varía por comunidad, así que `gastos_adquisicion` tiene una
    # fila por comunidad (region='Madrid', 'Cataluña'…) además de los conceptos
    # comunes a todo el país (region=''). Sin filtrar por región se sumarían las
    # 19 comunidades a la vez.
    #
    # La región sale de un mapa provincia → comunidad en BD (dato, no diccionario
    # en Python). Si el país tiene gastos por región y no logramos resolver la del
    # inmueble, NO se calcula por lo bajo: se inyecta un concepto con valor None,
    # que el motor trata como dato ausente y degrada la calidad. Rellenar el hueco
    # con solo los gastos comunes daría un coste de adquisición más barato de lo
    # real y un ROI inflado.
    todos_los_gastos = await config_mercado.listar_gastos_adquisicion(pais)
    region = await config_mercado.resolver_region(pais, inmueble.provincia)
    hay_gastos_por_region = any(g.region for g in todos_los_gastos)

    if hay_gastos_por_region and region is None:
        filas_gasto = [g for g in todos_los_gastos if not g.region]
        region_sin_resolver = True
    else:
        filas_gasto = [g for g in todos_los_gastos if not g.region or g.region == region]
        region_sin_resolver = False

    gastos = [
        mf.GastoAdquisicionEntrada(
            g.concepto, g.tipo.value, g.valor, g.moneda, g.exento_confotur
        )
        for g in filas_gasto
    ]
    if region_sin_resolver:
        gastos.append(
            mf.GastoAdquisicionEntrada(
                concepto=f"region_fiscal_no_resuelta[{inmueble.provincia or 'sin provincia'}]",
                tipo="PORCENTAJE", valor=None, moneda=None,
            )
        )

    bench = None
    if inmueble.ciudad:
        bench = await config_mercado.obtener_benchmark_zona(
            pais, inmueble.ciudad, inmueble.barrio
        )
    moneda_bench = bench.moneda if bench else None

    # Mapa de tasas: la moneda de cálculo es la del anuncio. Se leen de BD las
    # tasas de cada moneda de origen (coste, gastos fijos, benchmark) hacia ella.
    # La lee Python; el motor solo hace la aritmética. Falta una tasa → el motor
    # devuelve NO_CALCULABLE nombrando el par.
    moneda_calculo = inmueble.moneda
    fuentes: set[str] = set()
    if moneda_coste:
        fuentes.add(moneda_coste)
    if moneda_bench:
        fuentes.add(moneda_bench)
    for g in filas_gasto:
        if g.tipo.value == "FIJO" and g.moneda:
            fuentes.add(g.moneda)
    tasas: dict[tuple[str, str], Decimal] = {}
    if moneda_calculo:
        for origen in fuentes:
            if origen == moneda_calculo:
                continue
            tc = await configuracion_pais.obtener_tasa(origen, moneda_calculo)
            if tc is not None:
                tasas[(origen, moneda_calculo)] = tc.tasa

    entrada = mf.EntradaFinanciera(
        precio=inmueble.precio,
        superficie_util_m2=inmueble.superficie_util_m2,
        superficie_construida_m2=inmueble.superficie_construida_m2,
        gastos_comunidad_mes=inmueble.gastos_comunidad_mes,
        nivel_reforma=nivel,
        coste_reforma_m2=coste_m2,
        gastos_adquisicion=gastos,
        precio_m2_alquiler_medio=bench.precio_m2_alquiler_medio if bench else None,
        precio_m2_venta_medio=bench.precio_m2_venta_medio if bench else None,
        ltv=ltv_efectivo,
        tipo_interes_anual=tipo_interes,
        plazo_anos=int(supuestos.get("plazo_anos", 25)),
        vacancia_pct=Decimal(str(supuestos.get("vacancia_pct", 0))),
        gastos_gestion_pct=Decimal(str(supuestos.get("gastos_gestion_pct", 0))),
        moneda_calculo=moneda_calculo,
        moneda_coste_reforma=moneda_coste,
        moneda_benchmark=moneda_bench,
        tasas=tasas,
        # None = desconocido. El motor lo distingue de False y lo refleja en la
        # calidad del dato si hay conceptos exentos configurados para el país.
        tiene_confotur=inmueble.tiene_confotur,
    )
    snapshot_mercado = {
        "pais": pais,
        "region_fiscal": region,
        "moneda_calculo": moneda_calculo,
        "tiene_confotur": inmueble.tiene_confotur,
        "tipo_interes_anual": str(tipo_interes) if tipo_interes is not None else None,
        "ltv_max": str(ltv_max) if ltv_max is not None else None,
        "ltv_efectivo": str(ltv_efectivo),
        "tasas_usadas": {f"{o}->{d}": str(t) for (o, d), t in tasas.items()},
    }
    return entrada, snapshot_mercado


async def calcular(
    inmueble: Inmueble, analisis: AnalisisCualitativo | None, perfil: PerfilInversor
) -> mf.ResultadoFinanciero:
    entrada, _ = await construir_entrada(inmueble, analisis, perfil)
    return mf.calcular_metricas(entrada)


async def calcular_y_guardar(
    inmueble: Inmueble,
    analisis: AnalisisCualitativo | None,
    perfil_snapshot: PerfilInversor,
) -> mf.ResultadoFinanciero:
    """Calcula con el perfil dado y persiste la fila canónica de métricas."""
    entrada, snapshot_mercado = await construir_entrada(inmueble, analisis, perfil_snapshot)
    resultado = mf.calcular_metricas(entrada)

    ref = await configuracion_pais.moneda_referencia()
    metricas_ref, tasa, parcial = await conversion.convertir_dict(
        resultado.metricas, inmueble.moneda, ref
    )
    estado = resultado.estado_calidad
    if parcial and estado == CalidadDato.COMPLETO:
        estado = CalidadDato.PARCIAL

    await repo_metricas.guardar(
        inmueble_id=inmueble.id,
        version_motor=resultado.version_motor,
        moneda=inmueble.moneda,
        moneda_referencia=ref,
        tasa_cambio_usada=tasa,
        conversion_parcial=parcial,
        snapshot_supuestos=perfil_snapshot.supuestos or {},
        snapshot_mercado_pais=snapshot_mercado,
        snapshot_gastos=None,
        snapshot_coste_reforma=None,
        metricas={k: str(v) for k, v in resultado.metricas.items()},
        metricas_referencia=metricas_ref,
        inputs_auditoria=resultado.inputs_auditoria,
        estado_calidad=estado,
        campos_faltantes=(
            resultado.campos_faltantes + (["conversion_referencia"] if parcial else [])
        ),
    )
    return resultado
