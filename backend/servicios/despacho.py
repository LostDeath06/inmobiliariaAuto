"""Despacho de jobs a OpenClaw e ingesta del resultado.

Genera el job y el prompt; en modo http lo envía al VPS; en modo manual deja el
prompt listo para copiar desde la UI y espera el JSON pegado.
"""

from __future__ import annotations

import json
from uuid import UUID

from ..integraciones.openclaw_client import JobScraping, OpenClawClient, OpenClawError
from ..modelos.costes import FuenteUso
from ..modelos.openclaw import SobreScraping
from ..nucleo.config import obtener_config
from ..repositorios import (
    busquedas as repo_busquedas,
    jobs as repo_jobs,
    portales as repo_portales,
)
from . import constructor_prompt, costes, ingesta, pipeline


async def ejecutar_busqueda(busqueda_id: UUID) -> dict:
    """Crea un job, genera el prompt y lo despacha según el modo."""
    busqueda = await repo_busquedas.obtener(busqueda_id)
    if busqueda is None:
        raise ValueError("Búsqueda no existe")
    portal = await repo_portales.obtener(busqueda.portal_id)
    if portal is None:
        raise ValueError("Portal no existe")

    # Tope de gasto ANTES de crear nada: un job de OpenClaw es lo más caro que
    # hace el sistema (~1,75 USD estimado). Negarse a arrancar es limpio; no se
    # crea el job siquiera, así que no queda basura que limpiar después.
    cfg = obtener_config()
    permitido, motivo = await costes.comprobar_tope()
    if not permitido:
        return {"job_id": None, "modo": cfg.openclaw_mode, "estado": "NO_LANZADO",
                "error": motivo}

    job = await repo_jobs.crear(busqueda_id)
    prompt = constructor_prompt.construir(busqueda, portal, cfg.openclaw_limite_anuncios, str(job.id))
    await repo_jobs.actualizar(job.id, {"prompt_enviado": prompt})

    if cfg.openclaw_mode == "manual":
        # El prompt se copia desde la UI; el JSON se pega en /jobs/{id}/resultado-manual.
        await repo_jobs.actualizar(job.id, {"estado": "ENVIADO"})
        return {"job_id": str(job.id), "modo": "manual", "estado": "ENVIADO"}

    cliente = OpenClawClient()
    try:
        oc_id = await cliente.enviar_job(
            JobScraping(job_id=str(job.id), prompt=prompt,
                        limite_anuncios=cfg.openclaw_limite_anuncios)
        )
        await repo_jobs.actualizar(job.id, {"openclaw_job_id": oc_id, "estado": "EN_PROGRESO"})
        return {"job_id": str(job.id), "modo": "http", "estado": "EN_PROGRESO", "openclaw_job_id": oc_id}
    except OpenClawError as e:
        await repo_jobs.actualizar(job.id, {"estado": "FALLIDO", "error_mensaje": str(e)})
        return {"job_id": str(job.id), "modo": "http", "estado": "FALLIDO", "error": str(e)}


async def ingestar_resultado_manual(job_id: UUID, sobre_json: dict) -> dict:
    """Modo manual: valida el JSON pegado, ingesta y lanza el pipeline."""
    try:
        sobre = SobreScraping.model_validate(sobre_json)
    except Exception as e:
        await repo_jobs.actualizar(job_id, {"estado": "FALLIDO", "error_mensaje": str(e)})
        raise
    resumen = await ingesta.procesar(job_id, sobre)
    ids = [UUID(i) for i in resumen["inmuebles"]]
    proc = await pipeline.procesar_inmuebles(ids, job_id)
    return {**resumen, **proc}


async def procesar_job_http(job_id: UUID) -> dict:
    """Modo http: consulta el resultado en OpenClaw, ingesta y lanza el pipeline."""
    job = await repo_jobs.obtener(job_id)
    if job is None or not job.openclaw_job_id:
        return {"job_id": str(job_id), "estado": "SIN_OPENCLAW_ID"}
    cliente = OpenClawClient()
    try:
        sobre = await cliente.obtener_resultado(job.openclaw_job_id)
    except OpenClawError as e:
        await repo_jobs.actualizar(job_id, {"estado": "FALLIDO", "error_mensaje": str(e)})
        return {"job_id": str(job_id), "estado": "FALLIDO", "error": str(e)}
    # Consumo del agente: es la partida GRANDE del gasto y hasta ahora no se
    # anotaba en ningún sitio. Se registra antes del pipeline para que quede
    # aunque el análisis posterior falle.
    uso = await cliente.obtener_uso(job.openclaw_job_id)
    if uso:
        cfg = obtener_config()
        await costes.registrar_uso(
            fuente=FuenteUso.OPENCLAW,
            modelo=getattr(cfg, "openclaw_modelo", None) or cfg.anthropic_model,
            entrada=int(uso.get("input") or 0),
            salida=int(uso.get("output") or 0),
            cache_write=int(uso.get("cacheWrite") or 0),
            cache_read=int(uso.get("cacheRead") or 0),
            job_id=job_id,
            detalle={"total_reportado": uso.get("total")},
        )

    resumen = await ingesta.procesar(job_id, sobre)
    ids = [UUID(i) for i in resumen["inmuebles"]]
    proc = await pipeline.procesar_inmuebles(ids, job_id)
    return {**resumen, **proc}


async def reintentar_job(job_id: UUID) -> dict:
    """Reintenta un job fallido: re-despacha la búsqueda."""
    job = await repo_jobs.obtener(job_id)
    if job is None:
        raise ValueError("Job no existe")
    await repo_jobs.incrementar_intentos(job_id)
    return await ejecutar_busqueda(job.busqueda_id)
