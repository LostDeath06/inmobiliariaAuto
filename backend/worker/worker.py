"""Worker de jobs (APScheduler, sin Redis ni Celery — decisión 7A).

Sondea periódicamente:
1. Búsquedas activas con cron vencido → crea y despacha un job.
2. En modo http: jobs EN_PROGRESO → consulta OpenClaw y, si terminó, ingesta.

En modo manual el worker solo dispara las búsquedas con cron; el resultado lo pega
el usuario desde la UI.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ..integraciones.openclaw_client import OpenClawClient, OpenClawError
from ..nucleo.config import obtener_config
from ..repositorios import busquedas as repo_busquedas
from ..repositorios import jobs as repo_jobs
from ..servicios import despacho

log = logging.getLogger("worker")


def _proxima_ejecucion(expr: str) -> datetime | None:
    try:
        trigger = CronTrigger.from_crontab(expr, timezone=timezone.utc)
        return trigger.get_next_fire_time(None, datetime.now(timezone.utc))
    except Exception:
        return None


async def _despachar_cron() -> None:
    for busqueda in await repo_busquedas.listar_pendientes_de_cron():
        try:
            await despacho.ejecutar_busqueda(busqueda.id)
        except Exception as e:  # nunca tumbar el worker por una búsqueda
            log.warning("Fallo despachando búsqueda %s: %s", busqueda.id, e)
        finally:
            proxima = _proxima_ejecucion(busqueda.frecuencia_cron or "")
            await repo_busquedas.marcar_ejecutada(busqueda.id, proxima)


async def _procesar_jobs_http() -> None:
    cfg = obtener_config()
    if cfg.openclaw_mode != "http":
        return
    from ..modelos.enumeraciones import EstadoJob
    cliente = OpenClawClient()
    for job in await repo_jobs.listar(EstadoJob.EN_PROGRESO):
        if not job.openclaw_job_id:
            continue
        try:
            estado = await cliente.consultar_estado(job.openclaw_job_id)
        except OpenClawError as e:
            log.warning("Fallo consultando estado del job %s: %s", job.id, e)
            continue
        if estado.upper() in {"COMPLETED", "COMPLETADO", "DONE", "FINISHED"}:
            try:
                await despacho.procesar_job_http(job.id)
            except Exception as e:
                log.warning("Fallo procesando job http %s: %s", job.id, e)


async def tick() -> None:
    await _despachar_cron()
    await _procesar_jobs_http()


def iniciar() -> AsyncIOScheduler:
    cfg = obtener_config()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        tick, "interval", seconds=cfg.worker_intervalo_sondeo_segundos,
        id="tick", max_instances=1, coalesce=True,
    )
    scheduler.start()
    log.info("Worker iniciado (intervalo %ss)", cfg.worker_intervalo_sondeo_segundos)
    return scheduler


async def _principal() -> None:
    logging.basicConfig(level=logging.INFO)
    iniciar()
    while True:  # mantener vivo el proceso
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(_principal())
