"""Endpoints del dashboard de costes de tokens.

Todo lo que se muestra sale del libro `uso_tokens`, tarifado con `precios_modelo`.
Ninguna cifra se calcula aquí con precios de Python (Principio 2).
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, HTTPException

from ..modelos.costes import FuenteUso
from ..repositorios import configuracion_pais
from ..repositorios import uso_tokens as repo
from ..servicios import costes

router = APIRouter(prefix="/api/costes", tags=["costes"])


def _dec(v) -> Decimal | None:
    return None if v is None else Decimal(str(v))


@router.get("/resumen")
async def resumen():
    """Todo lo que la pantalla necesita de una vez: total, por fuente y umbrales."""
    return {
        "total": await repo.total(),
        "por_fuente": await repo.por_fuente(),
        "umbrales": await costes.estado_umbrales(),
        "registro_desde": await repo.registro_desde(),
    }


@router.get("/por-dia")
async def por_dia(dias: int = 30):
    return await repo.por_dia(dias)


@router.get("/por-job")
async def por_job(limite: int = 50):
    return await repo.por_job(limite)


@router.get("/por-inmueble")
async def por_inmueble(limite: int = 50):
    return await repo.por_inmueble(limite)


@router.get("/movimientos")
async def movimientos(limite: int = 100):
    """Últimas llamadas facturables, para auditar de dónde sale cada céntimo."""
    return await repo.listar(limite)


# --- Precios (editables: cambian, y Sonnet 5 sube el 1-sep-2026) -------------


@router.get("/precios")
async def listar_precios():
    return await repo.listar_precios()


@router.put("/precios")
async def establecer_precio(body: dict):
    if not body.get("modelo"):
        raise HTTPException(422, "Falta 'modelo'")
    return await repo.establecer_precio(
        modelo=body["modelo"],
        entrada=_dec(body.get("usd_entrada_por_m")) or Decimal(0),
        salida=_dec(body.get("usd_salida_por_m")) or Decimal(0),
        cache_write=_dec(body.get("usd_cache_write_por_m")) or Decimal(0),
        cache_read=_dec(body.get("usd_cache_read_por_m")) or Decimal(0),
        fuente=body.get("fuente"),
    )


@router.put("/tope")
async def establecer_tope(body: dict):
    """Tope que SÍ corta: por encima no se despacha trabajo nuevo."""
    if body.get("tope_gasto_diario_usd") is not None:
        await configuracion_pais.establecer_config_app(
            "tope_gasto_diario_usd", str(body["tope_gasto_diario_usd"])
        )
    return await costes.estado_umbrales()


@router.put("/umbrales")
async def establecer_umbrales(body: dict):
    """Umbrales de AVISO. No cortan la ejecución (eso es otra decisión)."""
    for clave in ("umbral_gasto_diario_usd", "umbral_gasto_total_usd"):
        if clave in body and body[clave] is not None:
            await configuracion_pais.establecer_config_app(clave, str(body[clave]))
    return await costes.estado_umbrales()


# --- Ingesta de uso de OpenClaw ---------------------------------------------


@router.post("/openclaw")
async def registrar_openclaw(body: dict):
    """El adaptador reporta aquí el `meta.agentMeta.usage` de cada job.

    Sin esto, TODO el consumo de OpenClaw —que es el grande— era invisible: el
    dashboard solo veía al analista, que resulta ser la parte barata.
    """
    uso = body.get("usage") or {}
    job_id = body.get("job_id")
    coste = await costes.registrar_uso(
        fuente=FuenteUso.OPENCLAW,
        modelo=body.get("modelo"),
        entrada=int(uso.get("input") or 0),
        salida=int(uso.get("output") or 0),
        cache_write=int(uso.get("cacheWrite") or 0),
        cache_read=int(uso.get("cacheRead") or 0),
        job_id=job_id,
        detalle={"total_reportado": uso.get("total"), "origen": "adaptador_openclaw"},
    )
    return {"registrado": True, "coste_usd": str(coste)}
