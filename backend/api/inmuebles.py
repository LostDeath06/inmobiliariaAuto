"""Endpoints de inmuebles, ranking y operaciones del pipeline."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException

from ..repositorios import (
    analisis as repo_analisis,
    config_mercado,
    inmuebles as repo_inmuebles,
    metricas as repo_metricas,
    scores as repo_scores,
)
from ..servicios import calculo_scoring, pipeline

router = APIRouter(prefix="/api", tags=["inmuebles-ranking"])


def _dec(v) -> Decimal | None:
    return None if v is None else Decimal(str(v))


@router.get("/ranking")
async def ranking(
    perfil_id: UUID,
    pais: str | None = None,
    sin_riesgo_pais: bool = False,
    limit: int = 50,
    incluir_obsoletos: bool = False,
):
    """El Top-N — la pantalla estrella.

    Salvaguardas: `pais` filtra por país; `sin_riesgo_pais` muestra el score bruto
    (sin el multiplicador de riesgo país) para detectar calibraciones que matan un
    mercado bueno.
    """
    return await repo_scores.ranking(
        perfil_id, pais=pais, sin_riesgo_pais=sin_riesgo_pais,
        limite=limit, incluir_obsoletos=incluir_obsoletos,
    )


@router.get("/inmuebles")
async def listar_inmuebles(
    pais: str | None = None, ciudad: str | None = None,
    precio_min: float | None = None, precio_max: float | None = None,
    limit: int = 100, offset: int = 0,
):
    return await repo_inmuebles.listar(
        pais=pais, ciudad=ciudad, precio_min=_dec(precio_min), precio_max=_dec(precio_max),
        limite=limit, desplazamiento=offset,
    )


@router.get("/inmuebles/{inmueble_id}")
async def ficha_inmueble(inmueble_id: UUID):
    """Ficha completa: datos, métricas con auditoría, análisis y scores por perfil."""
    inmueble = await repo_inmuebles.obtener(inmueble_id)
    if inmueble is None:
        raise HTTPException(404, "Inmueble no encontrado")
    # Perfil de la zona (para avisar en la ficha si es turística: el score de cashflow
    # no es representativo ahí). Se resuelve por (país, ciudad, barrio) del inmueble.
    zona = None
    if inmueble.ciudad:
        bench = await config_mercado.obtener_benchmark_zona(
            inmueble.pais or "", inmueble.ciudad, inmueble.barrio
        )
        if bench:
            zona = {
                "perfil_zona": bench.perfil_zona.value,
                "tiene_datos_corta": bench.adr_medio is not None and bench.ocupacion_media is not None,
            }
    return {
        "inmueble": inmueble,
        "zona": zona,
        "metricas": await repo_metricas.obtener(inmueble_id),
        "analisis": await repo_analisis.obtener(inmueble_id),
        "scores": await repo_scores.listar_por_inmueble(inmueble_id),
        "historico_precios": await repo_inmuebles.listar_historico_precios(inmueble_id),
    }


@router.get("/senales-no-reconocidas")
async def senales_no_reconocidas():
    """Monitor: inmuebles cuyo análisis trae códigos fuera del catálogo del país.

    Cada fila es un aviso de revisión: Claude devolvió un código que el catálogo del
    país no contempla (alucinación, o falta el código en el catálogo). Nunca se
    ignora en silencio.
    """
    return await repo_analisis.listar_senales_no_reconocidas()


@router.get("/inmuebles/{inmueble_id}/historico-precios")
async def historico_precios(inmueble_id: UUID):
    return await repo_inmuebles.listar_historico_precios(inmueble_id)


@router.post("/inmuebles/{inmueble_id}/recalcular")
async def recalcular(inmueble_id: UUID):
    return await pipeline.recalcular_inmueble(inmueble_id)


@router.post("/inmuebles/{inmueble_id}/recalcular-scores")
async def recalcular_scores(inmueble_id: UUID):
    """Solo scores (sin reanalizar): útil tras cambiar configuración de mercado."""
    return await calculo_scoring.calcular_todos_los_perfiles(inmueble_id)


@router.post("/pipeline/recalcular-todo")
async def recalcular_todo(perfil_id: UUID):
    """Tras cambiar pesos: recalcula los scores del perfil sobre todos los inmuebles."""
    return await pipeline.recalcular_todo_perfil(perfil_id)
