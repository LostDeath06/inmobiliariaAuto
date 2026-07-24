"""Endpoints de jobs (incluye modo manual de OpenClaw)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from ..modelos.enumeraciones import EstadoJob
from ..repositorios import anuncios as repo_anuncios
from ..repositorios import jobs as repo_jobs
from ..servicios import despacho

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
async def listar(estado: str | None = None):
    return await repo_jobs.listar(EstadoJob(estado) if estado else None)


@router.get("/{job_id}")
async def obtener(job_id: UUID):
    job = await repo_jobs.obtener(job_id)
    if job is None:
        raise HTTPException(404, "Job no encontrado")
    return job


@router.get("/{job_id}/prompt")
async def obtener_prompt(job_id: UUID):
    """Modo manual: devuelve el prompt para copiar."""
    job = await repo_jobs.obtener(job_id)
    if job is None:
        raise HTTPException(404, "Job no encontrado")
    return {"job_id": str(job_id), "prompt": job.prompt_enviado}


@router.post("/{job_id}/resultado-manual")
async def resultado_manual(job_id: UUID, body: dict):
    """Modo manual: ingesta el JSON pegado. `body` = el sobre de OpenClaw."""
    try:
        return await despacho.ingestar_resultado_manual(job_id, body)
    except Exception as e:
        raise HTTPException(422, f"JSON inválido o error de ingesta: {e}")


@router.get("/{job_id}/cuarentena")
async def cuarentena(job_id: UUID):
    """Anuncios en cuarentena del job (2A), consultables desde el monitor."""
    return await repo_anuncios.listar_cuarentena_de_job(job_id)


@router.post("/{job_id}/reintentar")
async def reintentar(job_id: UUID):
    try:
        return await despacho.reintentar_job(job_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/{job_id}/cancelar")
async def cancelar(job_id: UUID):
    """Aborta el job: mata el proceso de OpenClaw y anota el gasto ya hecho.

    Devuelve `proceso_abortado`. Si viene `false`, el estado es CANCELADO pero el
    agente puede seguir consumiendo: la UI tiene que decirlo, no celebrarlo.
    """
    try:
        return await despacho.cancelar_job(job_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    except despacho.EstadoNoCancelable as e:
        raise HTTPException(409, str(e)) from e


@router.post("/limpiar-zombis")
async def limpiar_zombis(minutos: int = 60):
    """Cierra como FALLIDO los jobs vivos parados desde hace más de `minutos`.

    Para el ruido que ya existe: jobs anteriores al timeout duro, que el
    adaptador olvidó al reiniciarse y que nadie va a resolver nunca. El worker
    evita que se creen nuevos; esto limpia los viejos.
    """
    cerrados = await repo_jobs.cerrar_zombis(minutos)
    return {
        "cerrados": len(cerrados),
        "minutos": minutos,
        "jobs": [{"id": str(j.id), "openclaw_job_id": j.openclaw_job_id} for j in cerrados],
    }
