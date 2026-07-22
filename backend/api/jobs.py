"""Endpoints de jobs (incluye modo manual de OpenClaw)."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException

from ..integraciones.openclaw_client import OpenClawClient
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
    job = await repo_jobs.obtener(job_id)
    if job is None:
        raise HTTPException(404, "Job no encontrado")
    if job.openclaw_job_id:
        await OpenClawClient().cancelar_job(job.openclaw_job_id)
    await repo_jobs.actualizar(job_id, {"estado": "CANCELADO"})
    return {"job_id": str(job_id), "estado": "CANCELADO"}
