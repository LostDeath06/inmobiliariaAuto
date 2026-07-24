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

from ..integraciones.openclaw_client import JobDesconocido, OpenClawClient, OpenClawError
from ..nucleo.config import obtener_config
from ..repositorios import busquedas as repo_busquedas
from ..repositorios import configuracion_pais as repo_config
from ..repositorios import jobs as repo_jobs
from ..servicios import despacho, sesiones_openclaw

log = logging.getLogger("worker")

# Las sesiones se leen cada 5 min, no en cada tick (15 s): son ficheros del disco
# del VPS y su gasto no cambia tan deprisa como para justificar el tráfico.
_ultima_ingesta_sesiones: datetime | None = None


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


_TERMINADO = {"COMPLETED", "COMPLETADO", "DONE", "FINISHED"}
_FALLIDO = {"FAILED", "FALLIDO", "ERROR"}
_CANCELADO = {"CANCELLED", "CANCELED", "CANCELADO"}


async def _limite(clave: str, por_defecto: int) -> int:
    """Parámetro operativo leído de BD (Principio 2: dato, no código)."""
    valor = await repo_config.obtener_config_app(clave)
    try:
        return int(str(valor))
    except (TypeError, ValueError):
        return por_defecto


def _segundos_vivo(job) -> float:
    """Cuánto lleva el job esperando. `created_at` es el respaldo para los jobs
    anteriores a que se rellenara `iniciado_en`."""
    desde = job.iniciado_en or job.created_at
    if desde is None:
        return 0.0
    if desde.tzinfo is None:
        desde = desde.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - desde).total_seconds()


async def _procesar_jobs_http() -> None:
    """Sondea los jobs vivos y, sobre todo, los cierra cuando toca.

    Antes esto solo miraba si el job había terminado. Si el adaptador se
    reiniciaba —y perdía su memoria— respondía 404, el worker lo registraba como
    un fallo cualquiera y volvía a preguntar al siguiente tick. Para siempre.
    Ningún camino llevaba a cerrar el job, así que quedaba EN_PROGRESO de por
    vida ensuciando los logs cada pocos segundos.

    Ahora hay tres salidas garantizadas: el adaptador lo da por terminado, el
    adaptador no lo reconoce N veces seguidas, o se agota el tiempo. Ninguna
    depende de que el adaptador colabore.
    """
    cfg = obtener_config()
    if cfg.openclaw_mode != "http":
        return

    max_404 = await _limite("max_sondeos_no_encontrado", 5)
    margen = await _limite("margen_timeout_job_segundos", 120)
    # El techo real: lo que el adaptador se concede (TIMEOUT + 60 para matar el
    # proceso) más un margen para que reporte. Pasado eso, nadie va a contestar.
    tope_seg = cfg.openclaw_timeout_segundos + 60 + margen

    cliente = OpenClawClient()
    for job in await repo_jobs.listar_vivos():
        # 1. Timeout duro. Se comprueba ANTES de preguntar: un job que lleva
        #    horas colgado no mejora por consultarlo una vez más.
        vivo_seg = _segundos_vivo(job)
        if vivo_seg > tope_seg:
            await repo_jobs.cerrar(job.id, "FALLIDO", (
                f"Timeout duro: el job lleva {int(vivo_seg // 60)} min sin terminar, "
                f"por encima del límite de {int(tope_seg // 60)} min "
                f"(OPENCLAW_TIMEOUT_SEGUNDOS={cfg.openclaw_timeout_segundos} + margen). "
                "Ningún job puede quedarse EN_PROGRESO para siempre."
            ))
            log.warning("Job %s cerrado por timeout duro (%.0f s)", job.id, vivo_seg)
            continue

        if not job.openclaw_job_id:
            continue  # PENDIENTE o manual: nada que consultar todavía

        # 2. Consulta al adaptador.
        try:
            estado = await cliente.consultar_estado(job.openclaw_job_id)
        except JobDesconocido:
            # El adaptador está vivo y dice que no conoce el job. Casi siempre
            # significa que se reinició y perdió su memoria (guarda los jobs en
            # un dict). Se le dan N oportunidades por si es un arranque a medias.
            fallos = await repo_jobs.contar_sondeo_no_encontrado(job.id)
            if fallos >= max_404:
                await repo_jobs.cerrar(job.id, "FALLIDO", (
                    "El adaptador no reconoce el job (¿reinicio?). "
                    f"Respondió 404 en {fallos} consultas seguidas. El adaptador guarda "
                    "los jobs en memoria, así que un reinicio los pierde y nadie va a "
                    "devolver ya un resultado. Se deja de consultar."
                ))
                log.warning("Job %s cerrado: 404 en %d consultas seguidas", job.id, fallos)
            continue
        except OpenClawError as e:
            # Caída real del adaptador: aquí sí toca esperar. El timeout duro de
            # arriba es la red que impide que esta espera sea infinita.
            log.warning("Fallo consultando estado del job %s: %s", job.id, e)
            continue

        await repo_jobs.reiniciar_sondeo_no_encontrado(job.id)

        # 3. Estados terminales del adaptador.
        estado_norm = (estado or "").upper()
        if estado_norm in _TERMINADO:
            try:
                await despacho.procesar_job_http(job.id)
            except Exception as e:
                log.warning("Fallo procesando job http %s: %s", job.id, e)
        elif estado_norm in _FALLIDO:
            # El adaptador ya sabe que falló: reflejarlo en vez de seguir
            # preguntando hasta que salte el timeout.
            await repo_jobs.cerrar(job.id, "FALLIDO", await _motivo_remoto(cliente, job))
        elif estado_norm in _CANCELADO:
            await repo_jobs.cerrar(job.id, "CANCELADO", await _motivo_remoto(cliente, job))


async def _motivo_remoto(cliente: OpenClawClient, job) -> str:
    """Motivo que da el adaptador, con el gasto parcial ya anotado."""
    motivo = "El adaptador cerró el job."
    try:
        motivo = (await cliente.consultar_job(job.openclaw_job_id)).get("error") or motivo
    except OpenClawError:
        pass
    # Un job que muere a mitad ya gastó: se anota antes de cerrar.
    try:
        await despacho.anotar_uso_del_job(cliente, job.id, job.openclaw_job_id)
    except Exception as e:  # noqa: BLE001 — la telemetría nunca tumba el worker
        log.warning("No se pudo anotar el gasto del job %s: %s", job.id, e)
    return motivo


async def _ingerir_sesiones() -> None:
    """Incorpora al libro el gasto de las conversaciones directas con el agente.

    Es el punto ciego del dashboard: hablar con OpenClaw por terminal o Telegram
    cuesta dinero real y no pasa por ninguna parte del sistema. Va aparte del
    sondeo de jobs porque no urge y no debe encarecer cada tick.
    """
    global _ultima_ingesta_sesiones
    ahora = datetime.now(timezone.utc)
    if _ultima_ingesta_sesiones and (ahora - _ultima_ingesta_sesiones).total_seconds() < 300:
        return
    _ultima_ingesta_sesiones = ahora
    try:
        resultado = await sesiones_openclaw.sincronizar()
        if resultado.get("nuevas_anotaciones"):
            log.info("Sesiones de OpenClaw: %s apuntes nuevos, $%s",
                     resultado["nuevas_anotaciones"], resultado.get("coste_usd"))
    except Exception as e:  # noqa: BLE001 — la telemetría nunca tumba el worker
        log.warning("No se pudieron leer las sesiones de OpenClaw: %s", e)


async def tick() -> None:
    await _despachar_cron()
    await _procesar_jobs_http()
    await _ingerir_sesiones()


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
