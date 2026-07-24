"""Cálculo y registro del coste de tokens.

PRINCIPIO 2 también aquí: los precios NO viven en Python. Se leen de
`precios_modelo`, que se edita desde la pantalla de Costes. Antes estaban
hardcodeados en pipeline.py ($3/$15) y además desactualizados: Sonnet 5 está a
$2/$10 en precio introductorio, así que el coste mostrado sobreestimaba el
analista un 50% mientras el gasto de OpenClaw era del todo invisible.

Si falta el precio de un modelo, el coste sale 0 y se deja constancia en
`detalle.aviso`: preferible un 0 que se ve y se explica a un número inventado.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from ..modelos.costes import FuenteUso, UsoTokens
from ..repositorios import uso_tokens as repo
from ..repositorios import configuracion_pais

_MILLON = Decimal(1_000_000)


async def calcular_coste(
    modelo: str | None,
    *,
    entrada: int = 0,
    salida: int = 0,
    cache_write: int = 0,
    cache_read: int = 0,
) -> tuple[Decimal, str | None]:
    """Coste en USD de una llamada. Devuelve (coste, aviso_si_falta_precio)."""
    if not modelo:
        return Decimal(0), "sin modelo: no se puede tarifar"
    precio = await repo.obtener_precio(modelo)
    if precio is None:
        return Decimal(0), (
            f"sin precio configurado para '{modelo}': el coste se anota como 0. "
            "Añádelo en la pantalla de Costes."
        )
    coste = (
        Decimal(entrada) * precio.usd_entrada_por_m
        + Decimal(salida) * precio.usd_salida_por_m
        + Decimal(cache_write) * precio.usd_cache_write_por_m
        + Decimal(cache_read) * precio.usd_cache_read_por_m
    ) / _MILLON
    return coste, None


async def registrar_uso(
    *,
    fuente: FuenteUso,
    modelo: str | None,
    entrada: int = 0,
    salida: int = 0,
    cache_write: int = 0,
    cache_read: int = 0,
    job_id: UUID | None = None,
    inmueble_id: UUID | None = None,
    detalle: dict | None = None,
) -> Decimal:
    """Tarifa y anota una llamada. Devuelve el coste."""
    if not any((entrada, salida, cache_write, cache_read)):
        return Decimal(0)
    coste, aviso = await calcular_coste(
        modelo, entrada=entrada, salida=salida,
        cache_write=cache_write, cache_read=cache_read,
    )
    info = dict(detalle or {})
    if aviso:
        info["aviso"] = aviso
    await repo.registrar(UsoTokens(
        fuente=fuente, modelo=modelo, job_id=job_id, inmueble_id=inmueble_id,
        tokens_entrada=entrada, tokens_salida=salida,
        tokens_cache_write=cache_write, tokens_cache_read=cache_read,
        coste_usd=coste, detalle=info,
    ))
    return coste


async def _umbral(clave: str, por_defecto: str) -> Decimal:
    valor = await configuracion_pais.obtener_config_app(clave)
    try:
        return Decimal(str(valor)) if valor else Decimal(por_defecto)
    except Exception:  # noqa: BLE001
        return Decimal(por_defecto)


class TopeGastoSuperado(Exception):
    """El gasto de hoy supera el tope: no se arranca trabajo nuevo."""


async def comprobar_tope() -> tuple[bool, str]:
    """¿Se puede arrancar trabajo nuevo? Devuelve (permitido, motivo).

    Se consulta ANTES de empezar algo caro, nunca a mitad: negarse a arrancar es
    limpio; matar un job en vuelo deja estado parcial.
    """
    tope = await _umbral("tope_gasto_diario_usd", "2.00")
    hoy = await repo.gasto_de_hoy()
    if hoy >= tope:
        return False, (
            f"Tope de gasto diario alcanzado: llevas ${hoy} de un tope de ${tope}. "
            "No se arranca trabajo nuevo. Súbelo en la pantalla de Costes si "
            "quieres continuar hoy."
        )
    return True, f"gasto de hoy ${hoy} de ${tope}"


async def exigir_tope() -> None:
    """Como `comprobar_tope`, pero lanza. Para puntos donde no hay que seguir."""
    permitido, motivo = await comprobar_tope()
    if not permitido:
        raise TopeGastoSuperado(motivo)


async def estado_umbrales() -> dict:
    """Compara el gasto con los umbrales configurados.

    SOLO avisa. Un tope que además CORTE la ejecución es otra decisión (y otro
    riesgo: un corte a mitad de lote deja inmuebles a medio procesar), así que
    no se hace sin pedirlo explícitamente.
    """
    hoy = await repo.gasto_de_hoy()
    tot = await repo.total()
    total_usd = Decimal(str(tot.get("coste_usd", 0) or 0))
    umbral_dia = await _umbral("umbral_gasto_diario_usd", "1.00")
    umbral_total = await _umbral("umbral_gasto_total_usd", "25.00")
    tope_dia = await _umbral("tope_gasto_diario_usd", "2.00")
    return {
        "gasto_hoy_usd": str(hoy),
        "umbral_diario_usd": str(umbral_dia),
        "supera_diario": hoy > umbral_dia,
        "gasto_total_usd": str(total_usd),
        "umbral_total_usd": str(umbral_total),
        "supera_total": total_usd > umbral_total,
        # El tope SÍ cambia el comportamiento: por encima no se despacha nada.
        "tope_diario_usd": str(tope_dia),
        "tope_alcanzado": hoy >= tope_dia,
    }
