"""Endpoints de portales y búsquedas."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException

from ..repositorios import busquedas as repo_busquedas
from ..repositorios import portales as repo_portales
from ..servicios import despacho

router = APIRouter(prefix="/api", tags=["portales-busquedas"])


def _dec(v) -> Decimal | None:
    return None if v is None else Decimal(str(v))


@router.get("/portales")
async def listar_portales():
    return await repo_portales.listar()


@router.post("/portales")
async def crear_portal(body: dict):
    return await repo_portales.crear(
        nombre=body["nombre"], url_raiz=body["url_raiz"], pais=body.get("pais"),
        notas_extraccion=body.get("notas_extraccion"),
    )


@router.get("/busquedas")
async def listar_busquedas():
    return await repo_busquedas.listar()


@router.post("/busquedas")
async def crear_busqueda(body: dict):
    return await repo_busquedas.crear(
        portal_id=UUID(body["portal_id"]), ciudad=body.get("ciudad"),
        presupuesto_min=_dec(body.get("presupuesto_min")),
        presupuesto_max=_dec(body.get("presupuesto_max")),
        moneda=body.get("moneda"), tipo_inmueble=body.get("tipo_inmueble"),
        filtros_extra=body.get("filtros_extra"), frecuencia_cron=body.get("frecuencia_cron"),
    )


@router.post("/busquedas/{busqueda_id}/ejecutar")
async def ejecutar_busqueda(busqueda_id: UUID):
    try:
        return await despacho.ejecutar_busqueda(busqueda_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
