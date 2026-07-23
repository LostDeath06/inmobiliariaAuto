"""Adaptador HTTP que envuelve OpenClaw en el VPS (§14).

NO modifica OpenClaw: lo invoca. El SaaS (en Docker) habla con estos endpoints
(POST /jobs, GET /jobs/{id}, GET /jobs/{id}/resultado, POST /jobs/{id}/cancelar,
GET /health) y este proceso traduce cada job a una ejecución real del agente.

CÓMO SE INVOCA OPENCLAW (y por qué así)
---------------------------------------
Se usa el CLI `openclaw agent`, que la documentación describe como: "runs a single
agent turn through the Gateway. It accepts a message and executes non-interactively
to completion, then returns results to stdout".

Se eligió el CLI frente a hablar el protocolo WebSocket del Gateway (`chat.send`)
porque:
  · Está pensado literalmente para esto: ejecución no interactiva hasta completar.
  · Separa stdout de stderr ("Diagnostics go to stderr so scripts can parse stdout
    directly"), que es justo lo que necesita un automatismo.
  · Trae `--timeout` propio, y `--message-file` evita límites de longitud de
    argumento y problemas de escapado con prompts largos.
  · Por dentro pasa igualmente por el Gateway, pero el CLI absorbe el handshake y
    el versionado del protocolo (v4 hoy). Implementarlo a mano obligaría a seguir
    el stream de eventos y a depender de la forma exacta de `session.operation`,
    que la documentación pública no detalla. Menos superficie que se rompa.

LO QUE NO ESTÁ DOCUMENTADO (y cómo se maneja)
---------------------------------------------
La forma exacta del envoltorio que imprime `--json` no aparece en la documentación.
Por eso NO se asume una clave concreta: `_localizar_sobre()` busca el objeto del
contrato §5.4 (el que nosotros mismos exigimos por system prompt) dentro de la
respuesta, venga plano, anidado o dentro de un bloque markdown. Si no aparece o no
valida, el job termina FALLIDO con el motivo y la salida cruda: nunca datos
inventados.

Para ver el envoltorio real de TU instalación:

    python3 adaptador_openclaw_vps.py --sonda "di hola en JSON"

Requisitos:  pip install fastapi uvicorn
Arranque:    uvicorn adaptador_openclaw_vps:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ValidationError

app = FastAPI(title="Adaptador OpenClaw")

# --- Configuración (variables de entorno del servicio systemd) ----------------
API_KEY = os.environ.get("OPENCLAW_API_KEY", "")
BIN = os.environ.get("OPENCLAW_BIN", "openclaw")
AGENT_ID = os.environ.get("OPENCLAW_AGENT_ID", "")          # opcional
MODELO = os.environ.get("OPENCLAW_MODELO", "")              # opcional: provider/model
TIMEOUT = int(os.environ.get("OPENCLAW_TIMEOUT_SEGUNDOS", "900"))
MAX_CONCURRENTES = int(os.environ.get("OPENCLAW_MAX_CONCURRENTES", "1"))
CONTRATO_PATH = os.environ.get(
    "OPENCLAW_CONTRATO_PATH",
    str(Path(__file__).resolve().parent.parent / "docs" / "PROMPT_PARA_OPENCLAW.md"),
)

_jobs: dict[str, dict] = {}
_semaforo = asyncio.Semaphore(MAX_CONCURRENTES)


# --- Contrato §5.4: validación del SOBRE ------------------------------------
# Solo el envoltorio. Cada anuncio lo valida el backend uno a uno para poder
# mandar los inválidos a cuarentena sin tumbar el lote (decisión 2A).
class SobreScraping(BaseModel):
    job_id: str
    portal_url: str
    fecha_extraccion_utc: str
    total_anuncios_extraidos: int
    anuncios: list[dict]
    extraccion_completa: bool
    portal_nombre: str | None = None
    total_resultados_detectados: int | None = None
    errores_navegacion: list[str] = []
    advertencias: list[str] = []
    busqueda_ejecutada: dict | None = None


class FalloOpenClaw(Exception):
    """OpenClaw no devolvió un resultado utilizable. El job muere aquí, no se inventa."""


def _auth(authorization: str | None) -> None:
    if API_KEY and authorization != f"Bearer {API_KEY}":
        raise HTTPException(401, "No autorizado")


def _contrato() -> str:
    """System prompt del contrato §5.4, inyectado en CADA llamada.

    Se inyecta por llamada (en vez de dejarlo en la config de OpenClaw) para que
    el contrato viaje versionado con el repo: si cambia el formato de salida,
    basta un git pull, sin tocar la configuración del VPS ni arriesgarse a que
    ambos se desincronicen.
    """
    try:
        texto = Path(CONTRATO_PATH).read_text(encoding="utf-8")
    except OSError as e:
        raise FalloOpenClaw(f"No se pudo leer el contrato en {CONTRATO_PATH}: {e}") from e
    # El fichero arranca con instrucciones para el humano ("Pega este texto…").
    # Lo que va detrás del primer separador es el contrato para el agente.
    _, sep, cuerpo = texto.partition("\n---\n")
    return (cuerpo if sep else texto).strip()


def _mensaje(job_id: str, prompt: str, limite: int) -> str:
    return (
        f"{_contrato()}\n\n"
        "---\n\n"
        "# JOB A EJECUTAR AHORA\n\n"
        f"job_id: {job_id}\n"
        f"limite_anuncios: {limite}\n\n"
        f"{prompt}\n\n"
        "---\n\n"
        "Responde ÚNICAMENTE con el JSON del contrato §5.4. Sin texto adicional, "
        "sin explicaciones y sin envolverlo en ```. El campo job_id debe valer "
        f"exactamente: {job_id}"
    )


def _json_de_texto(texto: str) -> dict | None:
    """Extrae un objeto JSON de un texto que puede traer ``` o prosa alrededor."""
    texto = texto.strip()
    if not texto:
        return None
    # Quitar vallas markdown ```json … ```
    valla = re.search(r"```(?:json)?\s*(.+?)```", texto, re.S)
    if valla:
        texto = valla.group(1).strip()
    if not texto.startswith("{"):
        # Quedarse con el primer objeto de nivel superior que aparezca
        i = texto.find("{")
        if i == -1:
            return None
        texto = texto[i:]
    # Recorte por llaves equilibradas: tolera basura detrás del objeto
    prof, fin = 0, None
    for i, ch in enumerate(texto):
        if ch == "{":
            prof += 1
        elif ch == "}":
            prof -= 1
            if prof == 0:
                fin = i + 1
                break
    if fin is None:
        return None
    try:
        val = json.loads(texto[:fin])
        return val if isinstance(val, dict) else None
    except json.JSONDecodeError:
        return None


_CLAVES_SOBRE = {"anuncios", "total_anuncios_extraidos", "extraccion_completa"}


def _es_sobre(d: object) -> bool:
    return isinstance(d, dict) and len(_CLAVES_SOBRE & set(d)) >= 2


def _localizar_sobre(nodo: object, prof: int = 0) -> dict | None:
    """Busca el sobre §5.4 dentro de la respuesta del CLI.

    El esquema del envoltorio de `--json` no está documentado, así que en vez de
    asumir una clave se busca el objeto que cumple el contrato: plano, anidado o
    serializado dentro de una cadena de texto.
    """
    if prof > 6:
        return None
    if _es_sobre(nodo):
        return nodo  # type: ignore[return-value]
    if isinstance(nodo, str):
        cand = _json_de_texto(nodo)
        return cand if _es_sobre(cand) else None
    if isinstance(nodo, dict):
        for v in nodo.values():
            if (hallado := _localizar_sobre(v, prof + 1)) is not None:
                return hallado
    if isinstance(nodo, list):
        for v in nodo:
            if (hallado := _localizar_sobre(v, prof + 1)) is not None:
                return hallado
    return None


async def _ejecutar_cli(mensaje: str, job_id: str) -> tuple[int, str, str]:
    """Lanza `openclaw agent` con el mensaje en un fichero. Devuelve (rc, out, err)."""
    if shutil.which(BIN) is None:
        raise FalloOpenClaw(
            f"No se encuentra el ejecutable '{BIN}' en el PATH del servicio. "
            "Comprueba OPENCLAW_BIN o el PATH de la unidad systemd."
        )

    fd, ruta = tempfile.mkstemp(prefix=f"job-{job_id}-", suffix=".txt")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(mensaje)

        cmd = [BIN, "agent", "--message-file", ruta, "--json",
               "--timeout", str(TIMEOUT),
               # Sesión propia por job: sin contexto heredado de ejecuciones previas.
               "--session-key", f"inmobiliaria:job:{job_id}"]
        if AGENT_ID:
            cmd += ["--agent", AGENT_ID]
        if MODELO:
            cmd += ["--model", MODELO]

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            # Margen sobre el --timeout propio del CLI: si este no corta, cortamos.
            out, err = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT + 60)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise FalloOpenClaw(
                f"OpenClaw no terminó en {TIMEOUT + 60}s; proceso abortado."
            ) from None
        return proc.returncode or 0, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")
    finally:
        try:
            os.unlink(ruta)
        except OSError:
            pass


async def ejecutar_openclaw(job_id: str, prompt: str, limite: int) -> dict:
    """Ejecuta el job en OpenClaw y devuelve el sobre §5.4 validado.

    Lanza FalloOpenClaw si algo va mal. Nunca devuelve datos inventados ni un
    sobre a medias: o sale el contrato válido, o el job es FALLIDO.
    """
    async with _semaforo:
        rc, out, err = await _ejecutar_cli(_mensaje(job_id, prompt, limite), job_id)

    if rc != 0:
        raise FalloOpenClaw(f"openclaw agent terminó con código {rc}. stderr: {err.strip()[:600]}")

    # stdout debería ser el envoltorio JSON; si no lo es, aún puede traer el sobre
    # como texto plano (según cómo el agente haya respondido).
    try:
        raiz: object = json.loads(out)
    except json.JSONDecodeError:
        raiz = out

    sobre = _localizar_sobre(raiz)
    if sobre is None:
        raise FalloOpenClaw(
            "La salida de OpenClaw no contiene el JSON del contrato §5.4. "
            f"stdout (primeros 800 car.): {out.strip()[:800] or '(vacío)'} | "
            f"stderr: {err.strip()[:300]}"
        )

    # job_id autoritativo: el nuestro. Si el agente devolvió otro, se corrige y
    # se deja constancia en advertencias (no se oculta).
    advertencias = list(sobre.get("advertencias") or [])
    if sobre.get("job_id") != job_id:
        advertencias.append(
            f"job_id devuelto por el agente ('{sobre.get('job_id')}') corregido al del job real."
        )
        sobre["job_id"] = job_id
    sobre["advertencias"] = advertencias
    sobre.setdefault("fecha_extraccion_utc", datetime.now(timezone.utc).isoformat())

    try:
        validado = SobreScraping.model_validate(sobre)
    except ValidationError as e:
        raise FalloOpenClaw(f"El JSON de OpenClaw no cumple el contrato §5.4: {e}") from e

    return validado.model_dump()


async def _procesar(job_id: str, prompt: str, limite: int) -> None:
    _jobs[job_id]["estado"] = "EN_PROGRESO"
    try:
        _jobs[job_id]["resultado"] = await ejecutar_openclaw(job_id, prompt, limite)
        _jobs[job_id]["estado"] = "COMPLETADO"
    except Exception as e:  # noqa: BLE001 — cualquier fallo mata el job, con motivo
        _jobs[job_id]["estado"] = "FALLIDO"
        _jobs[job_id]["error"] = str(e)
        print(f"[job {job_id}] FALLIDO: {e}", file=sys.stderr, flush=True)


@app.post("/jobs")
async def crear_job(cuerpo: dict, authorization: str | None = Header(default=None)):
    _auth(authorization)
    job_id = cuerpo.get("job_id") or str(uuid.uuid4())
    _jobs[job_id] = {"estado": "PENDIENTE", "resultado": None, "error": None}
    asyncio.create_task(
        _procesar(job_id, cuerpo.get("prompt", ""), int(cuerpo.get("limite_anuncios", 50)))
    )
    return {"job_id": job_id, "estado": "PENDIENTE"}


@app.get("/jobs/{job_id}")
async def estado_job(job_id: str, authorization: str | None = Header(default=None)):
    _auth(authorization)
    if job_id not in _jobs:
        raise HTTPException(404, "Job no encontrado")
    j = _jobs[job_id]
    return {"job_id": job_id, "estado": j["estado"], "error": j.get("error")}


@app.get("/jobs/{job_id}/resultado")
async def resultado_job(job_id: str, authorization: str | None = Header(default=None)):
    _auth(authorization)
    j = _jobs.get(job_id)
    if j is None:
        raise HTTPException(404, "Job no encontrado")
    if j["estado"] == "FALLIDO":
        raise HTTPException(409, f"Job FALLIDO: {j.get('error')}")
    if j["resultado"] is None:
        raise HTTPException(404, "Resultado no disponible todavía")
    return j["resultado"]


@app.post("/jobs/{job_id}/cancelar")
async def cancelar_job(job_id: str, authorization: str | None = Header(default=None)):
    _auth(authorization)
    if job_id in _jobs:
        _jobs[job_id]["estado"] = "CANCELADO"
    return {"job_id": job_id, "estado": "CANCELADO"}


@app.get("/health")
async def health():
    """Sano = el adaptador responde Y el binario de OpenClaw existe."""
    hay_bin = shutil.which(BIN) is not None
    return {
        "estado": "ok" if hay_bin else "degradado",
        "openclaw_bin": BIN,
        "openclaw_encontrado": hay_bin,
        "contrato": CONTRATO_PATH,
        "contrato_encontrado": Path(CONTRATO_PATH).is_file(),
        "jobs_en_memoria": len(_jobs),
    }


# --- Sonda: ver el envoltorio REAL de --json en esta máquina ------------------
async def _sonda(texto: str) -> None:
    print(f"Binario: {shutil.which(BIN) or 'NO ENCONTRADO'}")
    rc, out, err = await _ejecutar_cli(texto, "sonda")
    print(f"\n--- código de salida: {rc} ---")
    print("--- STDOUT (esto es lo que parsea el adaptador) ---")
    print(out or "(vacío)")
    print("--- STDERR ---")
    print(err or "(vacío)")
    try:
        print("\n--- claves de nivel superior del envoltorio ---")
        print(list(json.loads(out).keys()))
    except Exception:
        print("(stdout no es un JSON de nivel superior)")


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--sonda":
        asyncio.run(_sonda(sys.argv[2]))
    else:
        print(__doc__)
