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
            await repo_analisis.marcar_fallido(
                inmueble_id, resultado.modelo, resultado.error
            )
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
            "tokens_salida": tokens_out, "analisis_fallido": resultado.fallido,
            "motivo_fallo": resultado.error}


async def procesar_inmuebles(ids: list[UUID], job_id: UUID | None = None) -> dict:
    """Procesa una lista de inmuebles y acumula tokens/coste en el job."""
    tokens_in = tokens_out = 0
    fallidos = 0
    motivos: list[str] = []
    for inmueble_id in ids:
        r = await procesar_inmueble(inmueble_id)
        tokens_in += r.get("tokens_entrada", 0)
        tokens_out += r.get("tokens_salida", 0)
        if r.get("analisis_fallido"):
            fallidos += 1
            motivo = r.get("motivo_fallo")
            if motivo and motivo not in motivos:
                motivos.append(motivo)

    if job_id is not None:
        coste = (Decimal(tokens_in) / Decimal(1_000_000) * _USD_ENTRADA_POR_M
                 + Decimal(tokens_out) / Decimal(1_000_000) * _USD_SALIDA_POR_M)
        cambios: dict = {
            "tokens_entrada": tokens_in, "tokens_salida": tokens_out,
            "coste_estimado_usd": coste,
        }
        # Un coste de 0 con análisis fallidos significa que ni siquiera se llegó a
        # llamar a la API. Se escribe el motivo en el job para que salga en el
        # Monitor, en vez de dejar un 0.0000 mudo que obliga a mirar los logs.
        if fallidos:
            resumen = (
                f"{fallidos} de {len(ids)} análisis fallaron"
                + (" (0 tokens consumidos: la llamada a la API no llegó a completarse)"
                   if tokens_in == 0 else "")
                + (". Motivos: " + " | ".join(motivos[:3]) if motivos else "")
            )
            cambios["error_mensaje"] = resumen[:2000]
        await repo_jobs.actualizar(job_id, cambios)
    return {"procesados": len(ids), "analisis_fallidos": fallidos,
            "motivos_fallo": motivos,
            "tokens_entrada": tokens_in, "tokens_salida": tokens_out}


async def reprocesar_sin_analisis(limite: int = 500) -> dict:
    """Reprocesa los inmuebles sin análisis o con análisis fallido.

    El análisis NO se salta cuando falta configuración de mercado: `procesar_inmueble`
    lo intenta siempre, antes de las métricas. Así que un inmueble sin análisis es
    un análisis que FALLÓ (API caída, clave mala, JSON inválido), no uno pendiente.
    Esto lo reintenta en lote sin tocar los que ya salieron bien.
    """
    ids = await repo_analisis.listar_sin_analisis(limite)
    if not ids:
        return {"pendientes": 0, "procesados": 0, "analisis_fallidos": 0}
    resultado = await procesar_inmuebles(ids)
    return {"pendientes": len(ids), **resultado}


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
