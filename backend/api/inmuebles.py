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


@router.get("/inventario/resumen")
async def resumen_inventario(pais: str | None = None):
    """Cuántos inmuebles hay y en qué estado. Lo usa el ranking para no mostrar
    un "0 inmuebles" mudo cuando en realidad hay inmuebles que no pueden puntuar."""
    return await repo_inmuebles.resumen_inventario(pais)


@router.put("/inmuebles/{inmueble_id}/confotur")
async def fijar_confotur(inmueble_id: UUID, body: dict):
    """Marca si el inmueble está acogido a CONFOTUR (Ley 158-01, RD).

    `tiene_confotur`: true | false | null. NULL es DESCONOCIDO y es un valor
    legítimo, no una forma de borrar: el motor lo distingue de false y degrada la
    calidad del dato en vez de asumir que el inmueble paga el impuesto.
    Solo lo fija el propietario: Claude únicamente puede sugerirlo desde el análisis.
    """
    if "tiene_confotur" not in body:
        raise HTTPException(422, "Falta el campo tiene_confotur (true, false o null)")
    valor = body["tiene_confotur"]
    if valor is not None and not isinstance(valor, bool):
        raise HTTPException(422, "tiene_confotur debe ser true, false o null")
    inmueble = await repo_inmuebles.actualizar(inmueble_id, {"tiene_confotur": valor})
    if inmueble is None:
        raise HTTPException(404, "Inmueble no encontrado")
    # El coste de adquisición cambia, así que las métricas y los scores anteriores
    # ya no valen: se recalculan aquí mismo en vez de dejarlos obsoletos en silencio.
    await pipeline.recalcular_inmueble(inmueble_id)
    return {"inmueble_id": str(inmueble_id), "tiene_confotur": valor, "recalculado": True}


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
        # Estado del análisis aunque haya fallado: `analisis` filtra los fallidos,
        # así que sin esto la ficha no puede distinguir "pendiente" de "falló, y
        # este fue el motivo".
        "analisis_estado": await repo_analisis.obtener_estado(inmueble_id),
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


@router.post("/pipeline/reprocesar-sin-analisis")
async def reprocesar_sin_analisis(limite: int = 500):
    """Reintenta el análisis de los inmuebles que no lo tienen o lo tienen fallido.

    Útil tras arreglar la causa de un fallo (clave de API, modelo, red): los
    inmuebles ya ingestados no se vuelven a pedir a OpenClaw, solo se reanalizan.
    """
    return await pipeline.reprocesar_sin_analisis(limite)


@router.post("/pipeline/recalcular-todo")
async def recalcular_todo(perfil_id: UUID):
    """Tras cambiar pesos: recalcula los scores del perfil sobre todos los inmuebles."""
    return await pipeline.recalcular_todo_perfil(perfil_id)
