"""Adaptador HTTP para envolver OpenClaw en el VPS (entregable §14).

NO modifica OpenClaw: lo envuelve. Despliega este archivo en el VPS de Hostinger y
expón el puerto 8080. El SaaS habla con estos endpoints (POST /jobs, GET /jobs/{id},
GET /jobs/{id}/resultado, GET /health).

Sustituye `ejecutar_openclaw()` por la llamada real a tu OpenClaw (CLI, socket, etc.).

    pip install fastapi uvicorn
    uvicorn adaptador_openclaw_vps:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException

app = FastAPI(title="Adaptador OpenClaw")

API_KEY = os.environ.get("OPENCLAW_API_KEY", "")
_jobs: dict[str, dict] = {}  # job_id -> {estado, resultado}


def _auth(authorization: str | None) -> None:
    if API_KEY and authorization != f"Bearer {API_KEY}":
        raise HTTPException(401, "No autorizado")


async def ejecutar_openclaw(job_id: str, prompt: str, limite: int) -> dict:
    """SUSTITUIR: llama a tu OpenClaw real y devuelve el JSON del contrato §5.4."""
    # Ejemplo de esqueleto — reemplaza por tu integración real:
    #   proc = await asyncio.create_subprocess_exec("openclaw", "--prompt", prompt, ...)
    #   salida = await proc.stdout.read()
    #   return json.loads(salida)
    await asyncio.sleep(0)
    return {
        "job_id": job_id,
        "portal_url": "",
        "fecha_extraccion_utc": datetime.now(timezone.utc).isoformat(),
        "total_anuncios_extraidos": 0,
        "anuncios": [],
        "errores_navegacion": ["adaptador de ejemplo: sustituye ejecutar_openclaw()"],
        "advertencias": [],
        "extraccion_completa": False,
    }


async def _procesar(job_id: str, prompt: str, limite: int) -> None:
    _jobs[job_id]["estado"] = "EN_PROGRESO"
    try:
        _jobs[job_id]["resultado"] = await ejecutar_openclaw(job_id, prompt, limite)
        _jobs[job_id]["estado"] = "COMPLETADO"
    except Exception as e:  # noqa: BLE001
        _jobs[job_id]["estado"] = "FALLIDO"
        _jobs[job_id]["error"] = str(e)


@app.post("/jobs")
async def crear_job(cuerpo: dict, authorization: str | None = Header(default=None)):
    _auth(authorization)
    job_id = cuerpo["job_id"]
    _jobs[job_id] = {"estado": "PENDIENTE", "resultado": None}
    asyncio.create_task(
        _procesar(job_id, cuerpo.get("prompt", ""), int(cuerpo.get("limite_anuncios", 50)))
    )
    return {"job_id": job_id, "estado": "PENDIENTE"}


@app.get("/jobs/{job_id}")
async def estado_job(job_id: str, authorization: str | None = Header(default=None)):
    _auth(authorization)
    if job_id not in _jobs:
        raise HTTPException(404, "Job no encontrado")
    return {"job_id": job_id, "estado": _jobs[job_id]["estado"]}


@app.get("/jobs/{job_id}/resultado")
async def resultado_job(job_id: str, authorization: str | None = Header(default=None)):
    _auth(authorization)
    if job_id not in _jobs or _jobs[job_id]["resultado"] is None:
        raise HTTPException(404, "Resultado no disponible")
    return _jobs[job_id]["resultado"]


@app.post("/jobs/{job_id}/cancelar")
async def cancelar_job(job_id: str, authorization: str | None = Header(default=None)):
    _auth(authorization)
    if job_id in _jobs:
        _jobs[job_id]["estado"] = "CANCELADO"
    return {"job_id": job_id, "estado": "CANCELADO"}


@app.get("/health")
async def health():
    return {"estado": "ok"}
