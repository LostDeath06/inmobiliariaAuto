"""Aplicación FastAPI."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import config as api_config
from .api import inmuebles as api_inmuebles
from .api import jobs as api_jobs
from .api import perfiles as api_perfiles
from .api import portales as api_portales
from .integraciones.openclaw_client import OpenClawClient
from .nucleo import basedatos
from .nucleo.config import obtener_config
from .servicios.analista_cualitativo import verificar_sdk


@asynccontextmanager
async def ciclo_vida(app: FastAPI):
    # Falla ruidosamente al arrancar si el SDK de Anthropic no soporta lo que el
    # analista usa (tool use). Preferimos un contenedor que no arranca a que los
    # análisis fallen uno a uno en silencio, como pasó con `output_config`.
    verificar_sdk()
    await basedatos.obtener_pool()
    yield
    await basedatos.cerrar_pool()


app = FastAPI(title="Sourcing Inmobiliario", version="0.1.0", lifespan=ciclo_vida)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # mono-usuario auto-hospedado (4A)
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_perfiles.router)
app.include_router(api_config.router)
app.include_router(api_portales.router)
app.include_router(api_jobs.router)
app.include_router(api_inmuebles.router)


@app.get("/api/salud")
async def salud():
    """Health check + estado de OpenClaw."""
    cfg = obtener_config()
    try:
        await basedatos.obtener_uno("SELECT 1")
        bd_ok = True
    except Exception:
        bd_ok = False
    openclaw_ok = await OpenClawClient().health()
    return {
        "estado": "ok" if bd_ok else "degradado",
        "base_datos": bd_ok,
        "openclaw": {"modo": cfg.openclaw_mode, "disponible": openclaw_ok},
    }
