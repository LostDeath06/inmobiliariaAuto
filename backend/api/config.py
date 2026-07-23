"""Endpoints de configuración de mercado y por país."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException

from ..modelos.enumeraciones import NivelReforma
from ..repositorios import config_mercado, configuracion_pais
from ..servicios import estado_configuracion

router = APIRouter(prefix="/api/config", tags=["config"])


def _dec(v) -> Decimal | None:
    return None if v is None else Decimal(str(v))


# --- Estado de configuración por país (checklist de operatividad) ------------


@router.get("/estado-pais")
async def estado_todos():
    return await estado_configuracion.estado_todos()


@router.get("/estado-pais/{pais}")
async def estado_pais(pais: str):
    return await estado_configuracion.estado_pais(pais)


# --- Mercado por país --------------------------------------------------------


@router.get("/mercado-pais")
async def listar_mercado():
    return await configuracion_pais.listar_config_mercado()


@router.put("/mercado-pais/{pais}")
async def actualizar_mercado(pais: str, body: dict):
    r = await configuracion_pais.actualizar_config_mercado(pais, body)
    if r is None:
        raise HTTPException(404, "País no encontrado")
    return r


# --- Umbrales por (perfil, país) --------------------------------------------


@router.get("/umbrales")
async def listar_umbrales(perfil_id: UUID | None = None):
    return await configuracion_pais.listar_umbrales(perfil_id)


@router.put("/umbrales/{perfil_id}/{pais}")
async def actualizar_umbrales(perfil_id: UUID, pais: str, body: dict):
    r = await configuracion_pais.establecer_umbrales(perfil_id, pais, body)
    if r is None:
        raise HTTPException(404, "Umbral no encontrado")
    return r


# --- Costes de reforma -------------------------------------------------------


@router.get("/costes-reforma")
async def listar_costes(pais: str | None = None):
    return await config_mercado.listar_costes_reforma(pais)


@router.put("/costes-reforma")
async def establecer_coste(body: dict):
    return await config_mercado.establecer_coste_reforma(
        body["pais"], NivelReforma(body["nivel_reforma"]),
        _dec(body.get("coste_m2")), body.get("moneda"), body.get("fuente"),
    )


# --- Gastos de adquisición ---------------------------------------------------


@router.get("/gastos-adquisicion")
async def listar_gastos(pais: str | None = None):
    return await config_mercado.listar_gastos_adquisicion(pais)


@router.put("/gastos-adquisicion")
async def establecer_gasto(body: dict):
    return await config_mercado.establecer_gasto_adquisicion(
        pais=body["pais"], region=body.get("region", ""), concepto=body["concepto"],
        tipo=body["tipo"], valor=_dec(body.get("valor")), moneda=body.get("moneda"),
        fuente=body.get("fuente"),
        # Qué conceptos exime CONFOTUR es dato, no código (Principio 2).
        exento_confotur=bool(body.get("exento_confotur", False)),
    )


# --- Regiones fiscales (mapa provincia → comunidad autónoma) -----------------


@router.get("/regiones-fiscales")
async def listar_regiones(pais: str | None = None):
    return await config_mercado.listar_regiones_fiscales(pais)


@router.put("/regiones-fiscales")
async def establecer_region(body: dict):
    await config_mercado.establecer_region_fiscal(
        pais=body["pais"], provincia=body["provincia"], region=body["region"],
        fuente=body.get("fuente"),
    )
    return {"ok": True}


# --- Benchmarks de zona ------------------------------------------------------


@router.get("/benchmarks")
async def listar_benchmarks(pais: str | None = None):
    return await config_mercado.listar_benchmarks_zona(pais)


@router.put("/benchmarks")
async def establecer_benchmark(body: dict):
    fecha = date.fromisoformat(body["fecha_dato"]) if body.get("fecha_dato") else None
    return await config_mercado.establecer_benchmark(
        pais=body["pais"], ciudad=body["ciudad"], barrio=body.get("barrio"),
        moneda=body.get("moneda"),
        precio_m2_venta_medio=_dec(body.get("precio_m2_venta_medio")),
        precio_m2_alquiler_medio=_dec(body.get("precio_m2_alquiler_medio")),
        rentabilidad_bruta_media_zona=_dec(body.get("rentabilidad_bruta_media_zona")),
        fuente=body.get("fuente"), fecha_dato=fecha,
        # Perfil de zona y datos de corta estancia (turístico). Ver 0007.
        perfil_zona=body.get("perfil_zona"),
        adr_medio=_dec(body.get("adr_medio")),
        ocupacion_media=_dec(body.get("ocupacion_media")),
        gastos_gestion_corta_pct=_dec(body.get("gastos_gestion_corta_pct")),
    )


# --- Riesgos por país + catálogo --------------------------------------------


@router.get("/catalogo-riesgos")
async def catalogo():
    return await configuracion_pais.listar_catalogo_riesgos()


@router.get("/riesgos-pais/{pais}")
async def riesgos_pais(pais: str):
    return await configuracion_pais.listar_riesgos_pais(pais)


@router.put("/riesgos-pais/{pais}")
async def establecer_riesgo(pais: str, body: dict):
    await configuracion_pais.establecer_riesgo_pais(
        pais, body["codigo"], body.get("es_eliminatorio", False),
        _dec(body.get("penalizacion")),
    )
    return {"ok": True}


# --- Tipos de cambio (carga manual) -----------------------------------------


@router.put("/tipos-cambio")
async def cargar_tasa(body: dict):
    await configuracion_pais.cargar_tasa(
        moneda_origen=body["moneda_origen"], moneda_destino=body["moneda_destino"],
        tasa=Decimal(str(body["tasa"])), fuente=body.get("fuente"),
        fecha=date.fromisoformat(body["fecha"]) if body.get("fecha") else date.today(),
    )
    return {"ok": True}


# --- Moneda de referencia ----------------------------------------------------


@router.get("/moneda-referencia")
async def obtener_moneda_ref():
    return {"moneda_referencia": await configuracion_pais.moneda_referencia()}


@router.put("/moneda-referencia")
async def fijar_moneda_ref(body: dict):
    await configuracion_pais.establecer_config_app("moneda_referencia", body["moneda_referencia"])
    return {"moneda_referencia": body["moneda_referencia"]}
