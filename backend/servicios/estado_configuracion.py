"""Estado de configuración por país.

Genera el checklist de qué falta para que cada país sea operativo (que sus scores
salgan COMPLETO en vez de NO_CALCULABLE / PARCIAL). Es la lista de tareas del
propietario. No inventa nada: solo reporta qué datos están cargados y cuáles no.
"""

from __future__ import annotations

from ..modelos.enumeraciones import EstadoParametro
from ..repositorios import (
    config_mercado,
    configuracion_pais,
    paises as repo_paises,
    portales as repo_portales,
)

_NIVELES_CON_COSTE = {"COSMETICA", "MEDIA", "INTEGRAL"}


def _item(
    clave: str, ok: bool, detalle: str, provisional: bool = False,
    advertencia: str | None = None,
) -> dict:
    """`advertencia`: consecuencia real y silenciosa de que falte este dato.

    No es lo mismo "falta un dato y el inmueble sale NO_CALCULABLE" (ruidoso, se ve)
    que "falta un dato y el score sale igualmente, pero mal calibrado" (silencioso).
    Lo segundo lleva advertencia: es lo que puede engañar al propietario.
    """
    return {
        "clave": clave, "ok": ok, "provisional": provisional, "detalle": detalle,
        "advertencia": advertencia,
    }


async def estado_pais(pais: str) -> dict:
    items: list[dict] = []
    config = await configuracion_pais.obtener_config_mercado(pais)

    if config is None:
        items.append(_item("config_mercado", False, "Sin configuración de mercado"))
        return {"pais": pais, "operativo": False, "items": items}

    monedas = config.monedas_nativas or []
    al_contado = config.ltv_max is not None and config.ltv_max == 0

    # tipo de interés (no necesario si es al contado)
    if al_contado:
        items.append(_item("tipo_interes", True, "Al contado (ltv_max=0)"))
    else:
        ok = config.tipo_interes_anual is not None
        items.append(_item(
            "tipo_interes",
            ok,
            "Cargado" if ok else "Falta el tipo de interés hipotecario",
            provisional=config.tipo_interes_estado == EstadoParametro.PROVISIONAL,
        ))

    items.append(_item(
        "riesgo_pais", True, f"riesgo_pais = {config.riesgo_pais}",
        provisional=config.riesgo_pais_estado == EstadoParametro.PROVISIONAL,
    ))

    sat_ok = config.sat_rentabilidad_neta is not None and config.sat_descuento_mercado is not None
    items.append(_item(
        "saturaciones", sat_ok,
        "Cargadas" if sat_ok else "Faltan saturaciones de normalización",
        provisional=(config.sat_rentabilidad_estado == EstadoParametro.PROVISIONAL
                     or config.sat_descuento_estado == EstadoParametro.PROVISIONAL),
    ))

    # gastos de adquisición
    gastos = await config_mercado.listar_gastos_adquisicion(pais)
    faltan_gastos = [g.concepto for g in gastos if g.valor is None]
    ok_gastos = bool(gastos) and not faltan_gastos
    items.append(_item(
        "gastos_adquisicion", ok_gastos,
        "Cargados" if ok_gastos else (
            "Sin conceptos configurados" if not gastos
            else f"Faltan valores: {', '.join(faltan_gastos)}"
        ),
    ))

    # costes de reforma
    costes = {c.nivel_reforma.value: c for c in await config_mercado.listar_costes_reforma(pais)}
    faltan_costes = [n for n in _NIVELES_CON_COSTE
                     if n not in costes or costes[n].coste_m2 is None]
    items.append(_item(
        "costes_reforma", not faltan_costes,
        "Cargados" if not faltan_costes else f"Faltan €/m²: {', '.join(sorted(faltan_costes))}",
    ))

    # benchmarks de zona
    benchs = await config_mercado.listar_benchmarks_zona(pais)
    ok_bench = any(
        b.precio_m2_alquiler_medio is not None and b.precio_m2_venta_medio is not None
        for b in benchs
    )
    items.append(_item(
        "benchmarks_zona", ok_bench,
        f"{len(benchs)} zona(s) cargada(s)" if ok_bench else "Sin benchmarks de zona",
    ))

    # riesgos por país (catálogo aplicado)
    #
    # Sin catálogo el scoring NO falla: sigue puntuando, pero `riesgo_activo` queda sin
    # datos y NINGUNA señal cruza — ni los eliminatorios. Un inmueble con OKUPAS o
    # CARGAS entraría al ranking sin descartar ni penalizar. Es config que falta, no un
    # bug, pero es silencioso: por eso lleva advertencia explícita.
    riesgos = await configuracion_pais.listar_riesgos_pais(pais)
    items.append(_item(
        "riesgos_pais", bool(riesgos),
        f"{len(riesgos)} riesgo(s) configurado(s)" if riesgos
        else "Sin riesgos eliminatorios/ponderables configurados",
        advertencia=None if riesgos else (
            "Sin catálogo de riesgos: ninguna señal de riesgo se aplicará al score "
            "(ni descarte duro ni penalización). Los inmuebles de este país pueden "
            "estar infra-penalizados."
        ),
    ))

    # fuente de anuncios: ¿hay de dónde sacar inmuebles para este país?
    #
    # Un país sin fuente aparece vacío en el ranking; sin este ítem parecería un fallo.
    # Los portales probados que bloquean el acceso quedan registrados como inactivos
    # (con nota), para que la app diga POR QUÉ está vacío, no lo calle.
    portales_pais = await repo_portales.listar_por_pais(pais)
    activos = [p for p in portales_pais if p.activo]
    bloqueados = [p for p in portales_pais if not p.activo]
    if activos:
        items.append(_item(
            "fuente_anuncios", True,
            f"{len(activos)} portal(es): {', '.join(p.nombre for p in activos)}",
        ))
    elif bloqueados:
        lista = ", ".join(p.nombre for p in bloqueados)
        items.append(_item(
            "fuente_anuncios", False,
            "Sin fuente de anuncios disponible — todos los portales probados bloquean acceso automatizado.",
            advertencia=(
                f"Portales probados que bloquean el acceso automatizado: {lista}. "
                "Hace falta una fuente que no bloquee (web de agencia, export, carga manual) "
                "o montar OpenClaw. Por eso este país sale vacío: no es un fallo."
            ),
        ))
    else:
        items.append(_item(
            "fuente_anuncios", False,
            "Sin portal de anuncios registrado para este país.",
        ))

    # tipos de cambio a la moneda de referencia
    ref = await configuracion_pais.moneda_referencia()
    faltan_tasas = []
    for m in monedas:
        if m == ref:
            continue
        if await configuracion_pais.obtener_tasa(m, ref) is None:
            faltan_tasas.append(f"{m}→{ref}")
    items.append(_item(
        "tipos_cambio", not faltan_tasas,
        "Cargados" if not faltan_tasas else f"Faltan tasas: {', '.join(faltan_tasas)}",
    ))

    operativo = all(i["ok"] for i in items)
    return {"pais": pais, "operativo": operativo, "items": items}


async def estado_todos() -> list[dict]:
    resultado = []
    for p in await repo_paises.listar():
        resultado.append(await estado_pais(p.codigo))
    return resultado
