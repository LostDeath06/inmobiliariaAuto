"""Despacho de jobs a OpenClaw e ingesta del resultado.

Genera el job y el prompt; en modo http lo envía al VPS; en modo manual deja el
prompt listo para copiar desde la UI y espera el JSON pegado.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from ..integraciones.openclaw_client import JobScraping, OpenClawClient, OpenClawError
from ..modelos.costes import FuenteUso
from ..modelos.enumeraciones import EstadoJob
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
        # `iniciado_en` no es cosmético: es la referencia del timeout duro. Sin
        # él, un job que se cuelga no tiene contra qué medirse y vive para
        # siempre. Antes no se rellenaba nunca.
        await repo_jobs.actualizar(job.id, {
            "openclaw_job_id": oc_id, "estado": "EN_PROGRESO",
            "iniciado_en": datetime.now(timezone.utc),
        })
        return {"job_id": str(job.id), "modo": "http", "estado": "EN_PROGRESO", "openclaw_job_id": oc_id}
    except OpenClawError as e:
        await repo_jobs.cerrar(job.id, "FALLIDO", str(e))
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
    await anotar_uso_del_job(cliente, job_id, job.openclaw_job_id)

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


# --- Cancelación -------------------------------------------------------------

# Estados desde los que se puede cancelar. Fuera de aquí no hay nada que parar,
# y ofrecerlo sería prometer algo que el botón no puede cumplir.
CANCELABLES = {EstadoJob.PENDIENTE, EstadoJob.ENVIADO, EstadoJob.EN_PROGRESO}


class EstadoNoCancelable(Exception):
    """El job ya está en un estado terminal."""


async def anotar_uso_del_job(cliente: OpenClawClient, job_id: UUID, oc_id: str) -> dict | None:
    """Lee el consumo del job en el adaptador y lo anota en el libro.

    Se llama tanto al completar como al cancelar. Un job cancelado a mitad YA
    gastó tokens: dejarlo sin anotar haría que el dashboard mintiese justo en el
    caso en que uno mira el dashboard.
    """
    uso, parcial = await cliente.obtener_uso(oc_id)
    if not uso:
        return None
    cfg = obtener_config()
    coste = await costes.registrar_uso(
        fuente=FuenteUso.OPENCLAW,
        modelo=getattr(cfg, "openclaw_modelo", None) or cfg.anthropic_model,
        entrada=int(uso.get("input") or 0),
        salida=int(uso.get("output") or 0),
        cache_write=int(uso.get("cacheWrite") or 0),
        cache_read=int(uso.get("cacheRead") or 0),
        job_id=job_id,
        detalle={
            "total_reportado": uso.get("total"),
            "parcial": parcial,
            **({"aviso_parcial": (
                "El job murió antes de terminar. Este consumo es el que alcanzó a "
                "reportar el agente: lo gastado de verdad puede ser algo mayor."
            )} if parcial else {}),
        },
    )
    return {"uso": uso, "parcial": parcial, "coste_usd": str(coste)}


async def cancelar_job(job_id: UUID) -> dict:
    """Cancela un job: aborta el proceso, anota lo gastado y cierra el estado.

    El orden importa. Primero se manda parar (cuanto antes deje de gastar,
    mejor), después se lee el consumo —ya definitivo, porque el proceso murió— y
    solo al final se marca CANCELADO. Al revés, la UI diría "cancelado" antes de
    que nada estuviera parado.
    """
    job = await repo_jobs.obtener(job_id)
    if job is None:
        raise ValueError("Job no existe")
    if job.estado not in CANCELABLES:
        raise EstadoNoCancelable(
            f"El job está {job.estado.value}: ya terminó, no hay nada que cancelar."
        )

    respuesta: dict = {"proceso_abortado": True, "detalle": "el job no llegó a salir del backend"}
    gasto = None
    if job.openclaw_job_id:
        cliente = OpenClawClient()
        respuesta = await cliente.cancelar_job(job.openclaw_job_id)
        # El adaptador necesita un instante para cerrar el job y volcar el uso
        # parcial; si no está listo, se anota lo que haya y no se bloquea nada.
        gasto = await anotar_uso_del_job(cliente, job_id, job.openclaw_job_id)

    abortado = bool(respuesta.get("proceso_abortado"))
    motivo = "Cancelado desde el Monitor."
    if not abortado:
        # Principio 3: si el proceso pudo sobrevivir, se dice. Un "CANCELADO"
        # limpio sobre un agente que sigue gastando es el peor resultado posible.
        motivo += (
            " AVISO: el adaptador NO confirmó que el proceso de OpenClaw haya muerto"
            f" ({respuesta.get('detalle') or 'sin detalle'}). Puede seguir consumiendo"
            " tokens: compruébalo en el VPS."
        )
    await repo_jobs.cerrar(job_id, "CANCELADO", motivo)
    return {
        "job_id": str(job_id),
        "estado": "CANCELADO",
        "proceso_abortado": abortado,
        "detalle": respuesta.get("detalle"),
        "gasto_parcial": gasto,
    }
