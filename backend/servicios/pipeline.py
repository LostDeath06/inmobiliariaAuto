"""Orquestación del pipeline post-ingesta: análisis cualitativo → métricas →
scores. Cada paso es idempotente y reejecutable. Un fallo en un inmueble se marca
y el pipeline sigue con los demás (nunca aborta el lote).
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from ..repositorios import (
    analisis as repo_analisis,
    configuracion_pais,
    inmuebles as repo_inmuebles,
    jobs as repo_jobs,
    perfiles as repo_perfiles,
    scores as repo_scores,
)
from . import analista_cualitativo, calculo_financiero, calculo_scoring

# Precios de la API (operativo, no criterio de inversión) — USD por millón de tokens.
_USD_ENTRADA_POR_M = Decimal("3")
_USD_SALIDA_POR_M = Decimal("15")


async def _codigos_pais(pais: str) -> tuple[list[str], list[str]]:
    """Códigos de riesgo (del país) y oportunidad (del catálogo) para el analista."""
    riesgos = await configuracion_pais.listar_riesgos_pais(pais)
    codigos_riesgo = [r.codigo for r in riesgos]
    catalogo = await configuracion_pais.listar_catalogo_riesgos()
    codigos_oport = [c.codigo for c in catalogo if c.clase.value == "OPORTUNIDAD"]
    return codigos_riesgo, codigos_oport


async def procesar_inmueble(inmueble_id: UUID) -> dict:
    """Análisis (con caché por hash) + métricas + scores de un inmueble."""
    inmueble = await repo_inmuebles.obtener(inmueble_id)
    if inmueble is None:
        return {"inmueble": str(inmueble_id), "error": "no existe"}

    tokens_in = tokens_out = 0
    codigos_riesgo, codigos_oport = await _codigos_pais(inmueble.pais or "")

    # 1. Análisis cualitativo (cacheado: si el anuncio no cambió, no reanaliza).
    resultado = await analista_cualitativo.analizar(inmueble, codigos_riesgo, codigos_oport)
    hash_previo = await repo_analisis.obtener_hash(inmueble_id)
    if hash_previo != resultado.hash_contenido:
        if resultado.fallido or resultado.analisis is None:
            await repo_analisis.marcar_fallido(inmueble_id, resultado.modelo)
        else:
            await repo_analisis.guardar(
                inmueble_id, resultado.analisis,
                hash_contenido=resultado.hash_contenido, modelo=resultado.modelo,
            )
        tokens_in += resultado.tokens_entrada
        tokens_out += resultado.tokens_salida

    analisis = await repo_analisis.obtener(inmueble_id)

    # 2. Métricas canónicas (perfil predeterminado, para la ficha de detalle).
    perfil_pred = await repo_perfiles.obtener_predeterminado()
    if perfil_pred:
        await calculo_financiero.calcular_y_guardar(inmueble, analisis, perfil_pred)

    # 3. Scores por cada perfil.
    await calculo_scoring.calcular_todos_los_perfiles(inmueble_id)

    return {"inmueble": str(inmueble_id), "tokens_entrada": tokens_in,
            "tokens_salida": tokens_out, "analisis_fallido": resultado.fallido}


async def procesar_inmuebles(ids: list[UUID], job_id: UUID | None = None) -> dict:
    """Procesa una lista de inmuebles y acumula tokens/coste en el job."""
    tokens_in = tokens_out = 0
    fallidos = 0
    for inmueble_id in ids:
        r = await procesar_inmueble(inmueble_id)
        tokens_in += r.get("tokens_entrada", 0)
        tokens_out += r.get("tokens_salida", 0)
        if r.get("analisis_fallido"):
            fallidos += 1

    if job_id is not None:
        coste = (Decimal(tokens_in) / Decimal(1_000_000) * _USD_ENTRADA_POR_M
                 + Decimal(tokens_out) / Decimal(1_000_000) * _USD_SALIDA_POR_M)
        await repo_jobs.actualizar(job_id, {
            "tokens_entrada": tokens_in, "tokens_salida": tokens_out,
            "coste_estimado_usd": coste,
        })
    return {"procesados": len(ids), "analisis_fallidos": fallidos,
            "tokens_entrada": tokens_in, "tokens_salida": tokens_out}


async def recalcular_inmueble(inmueble_id: UUID) -> dict:
    """Rehace análisis + métricas + score de un inmueble."""
    return await procesar_inmueble(inmueble_id)


async def recalcular_todo_perfil(perfil_id: UUID, limite: int = 1000) -> dict:
    """Tras cambiar pesos: recalcula los scores del perfil sobre todos los inmuebles."""
    inmuebles = await repo_inmuebles.listar(limite=limite)
    perfil = await repo_perfiles.obtener(perfil_id)
    if perfil is None:
        return {"error": "perfil no existe"}
    n = 0
    for inm in inmuebles:
        analisis = await repo_analisis.obtener(inm.id)
        await calculo_scoring.calcular_score_perfil(inm, analisis, perfil)
        n += 1
    return {"perfil_id": str(perfil_id), "recalculados": n}
