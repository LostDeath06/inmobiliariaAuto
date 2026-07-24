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
import contextlib
import json
import os
import re
import shutil
import signal
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ValidationError

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
# Estado en disco: sin esto un `systemctl restart` deja al backend consultando
# para siempre un job que el adaptador ya no reconoce (404 en bucle cada 3 s).
ESTADO_PATH = Path(os.environ.get("OPENCLAW_ESTADO_PATH", "/var/lib/openclaw-adaptador/jobs.json"))
# Sesiones de conversación del agente (fuera del sistema: terminal, Telegram).
RAIZ_SESIONES = Path(os.environ.get("OPENCLAW_SESIONES_PATH", "/root/.openclaw/agents"))
# Segundos entre SIGTERM y SIGKILL al abortar un job.
GRACIA_KILL = float(os.environ.get("OPENCLAW_GRACIA_KILL_SEG", "5"))

_jobs: dict[str, dict] = {}
_semaforo = asyncio.Semaphore(MAX_CONCURRENTES)

# Estados en los que un job todavía puede consumir tokens.
_VIVOS = {"PENDIENTE", "EN_PROGRESO"}

# Claves que NO se serializan a disco: son objetos de proceso, no datos.
_NO_PERSISTIBLE = {"proc"}


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
    """OpenClaw no devolvió un resultado utilizable. El job muere aquí, no se inventa.

    Lleva el `uso` que se haya podido rescatar de la salida parcial: un job que
    muere a mitad YA consumió tokens. Anotarlos como si no hubiera pasado nada
    dejaría un agujero en el libro de costes justo en el caso más caro.
    """

    def __init__(self, mensaje: str, uso: dict | None = None):
        super().__init__(mensaje)
        self.uso = uso


def _auth(authorization: str | None) -> None:
    if API_KEY and authorization != f"Bearer {API_KEY}":
        raise HTTPException(401, "No autorizado")


# --- Persistencia del estado -------------------------------------------------
# `_jobs` en memoria era suficiente mientras nadie reiniciaba el servicio. No lo
# es: al reiniciar, el adaptador olvidaba los jobs y respondía 404 a un backend
# que los tenía como EN_PROGRESO, para siempre. Ahora el estado sobrevive al
# reinicio y, sobre todo, los jobs que estaban vivos se cierran como FALLIDO con
# el motivo real — porque su subproceso murió con el servicio.


def _guardar_estado() -> None:
    """Vuelca `_jobs` a disco. Nunca tumba el flujo: perder la foto es malo,
    perder el job es peor."""
    try:
        ESTADO_PATH.parent.mkdir(parents=True, exist_ok=True)
        datos = {
            jid: {k: v for k, v in j.items() if k not in _NO_PERSISTIBLE}
            for jid, j in _jobs.items()
        }
        tmp = ESTADO_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        tmp.replace(ESTADO_PATH)  # atómico: un corte no deja un JSON a medias
    except OSError as e:
        print(f"[adaptador] no se pudo guardar {ESTADO_PATH}: {e}", file=sys.stderr, flush=True)


def _cargar_estado() -> None:
    """Recupera el estado al arrancar y cierra los jobs huérfanos del reinicio."""
    if not ESTADO_PATH.is_file():
        print(
            f"[adaptador] AVISO: memoria de jobs VACÍA (no existe {ESTADO_PATH}). "
            "Cualquier job que el backend tenga como EN_PROGRESO es huérfano: su "
            "proceso ya no existe. El backend lo marcará FALLIDO tras varios 404.",
            file=sys.stderr, flush=True,
        )
        return
    try:
        _jobs.update(json.loads(ESTADO_PATH.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as e:
        print(f"[adaptador] no se pudo leer {ESTADO_PATH}: {e}", file=sys.stderr, flush=True)
        return

    # Un job que figuraba vivo no sobrevive al reinicio: su subproceso murió con
    # el servicio. Decirlo es mejor que responder 404 y que el backend adivine.
    huerfanos = [jid for jid, j in _jobs.items() if j.get("estado") in _VIVOS]
    for jid in huerfanos:
        _jobs[jid]["estado"] = "FALLIDO"
        _jobs[jid]["error"] = (
            "El adaptador se reinició mientras el job estaba en curso; el proceso "
            "de OpenClaw murió con él. El job no llegó a devolver datos."
        )
    if huerfanos:
        print(
            f"[adaptador] {len(huerfanos)} job(s) marcados FALLIDO por reinicio: "
            + ", ".join(huerfanos),
            file=sys.stderr, flush=True,
        )
        _guardar_estado()
    print(f"[adaptador] estado recuperado: {len(_jobs)} job(s) en memoria",
          file=sys.stderr, flush=True)


@contextlib.asynccontextmanager
async def _ciclo_vida(_app: FastAPI):
    _cargar_estado()
    yield


app = FastAPI(title="Adaptador OpenClaw", lifespan=_ciclo_vida)


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


_CLAVES_USO = {"input", "output", "cacheWrite", "cacheRead", "total"}


def _localizar_usage(nodo: object, prof: int = 0) -> dict | None:
    """Busca el bloque de consumo (meta.agentMeta.usage) en la salida del CLI.

    Se busca por FORMA, no por ruta: el esquema del envoltorio de --json no está
    documentado y ya nos mordió una vez asumir una clave. Cualquier dict con al
    menos dos de {input, output, cacheWrite, cacheRead, total} vale.
    """
    if prof > 8:
        return None
    if isinstance(nodo, dict):
        if len(_CLAVES_USO & set(nodo)) >= 2 and any(
            isinstance(nodo.get(k), (int, float)) for k in _CLAVES_USO
        ):
            return nodo
        for v in nodo.values():
            if (h := _localizar_usage(v, prof + 1)) is not None:
                return h
    if isinstance(nodo, list):
        for v in nodo:
            if (h := _localizar_usage(v, prof + 1)) is not None:
                return h
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


def sesion_de_job(job_id: str) -> str:
    """Clave de sesión de un job. Una por job: sin contexto heredado (§9.4).

    También sirve para distinguir, al leer las sesiones del disco, cuáles son de
    jobs —ya contabilizados— y cuáles son conversaciones directas con el agente.
    """
    return f"inmobiliaria:job:{job_id}"


async def _abortar_proceso(proc: asyncio.subprocess.Process) -> bool:
    """Termina el proceso y TODOS sus hijos. Devuelve True si acabó muerto.

    SIGTERM al grupo, y si no se va en `GRACIA_KILL` segundos, SIGKILL. Se mata
    el grupo entero porque el CLI de OpenClaw lanza hijos: matar solo al padre
    deja tokens corriendo detrás de una etiqueta que dice "cancelado".
    """
    if proc.returncode is not None:
        return True

    def _senal(sig: int) -> None:
        if os.name == "posix":
            with contextlib.suppress(ProcessLookupError, PermissionError, OSError):
                os.killpg(os.getpgid(proc.pid), sig)
                return
        with contextlib.suppress(ProcessLookupError):
            proc.terminate() if sig == signal.SIGTERM else proc.kill()

    _senal(signal.SIGTERM)
    try:
        await asyncio.wait_for(proc.wait(), timeout=GRACIA_KILL)
        return True
    except asyncio.TimeoutError:
        pass

    _senal(getattr(signal, "SIGKILL", signal.SIGTERM))
    try:
        await asyncio.wait_for(proc.wait(), timeout=GRACIA_KILL)
        return True
    except asyncio.TimeoutError:
        # No mentir: si el proceso sigue vivo, quien pregunte tiene que saberlo.
        return False


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
               "--session-key", sesion_de_job(job_id)]
        if AGENT_ID:
            cmd += ["--agent", AGENT_ID]
        if MODELO:
            cmd += ["--model", MODELO]

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            # Grupo de procesos propio: `openclaw agent` lanza hijos (gateway,
            # navegador). Matar solo al padre dejaría a los hijos consumiendo
            # tokens mientras la app dice "cancelado" — peor que no cancelar.
            start_new_session=(os.name == "posix"),
        )
        # Visible para /jobs/{id}/cancelar: sin esta referencia, cancelar solo
        # podía cambiar una etiqueta.
        if job_id in _jobs:
            _jobs[job_id]["proc"] = proc
        try:
            # Margen sobre el --timeout propio del CLI: si este no corta, cortamos.
            out, err = await asyncio.wait_for(proc.communicate(), timeout=TIMEOUT + 60)
        except asyncio.TimeoutError:
            await _abortar_proceso(proc)
            raise FalloOpenClaw(
                f"OpenClaw no terminó en {TIMEOUT + 60}s; proceso abortado."
            ) from None
        finally:
            if job_id in _jobs:
                _jobs[job_id].pop("proc", None)
        return proc.returncode or 0, out.decode("utf-8", "replace"), err.decode("utf-8", "replace")
    finally:
        try:
            os.unlink(ruta)
        except OSError:
            pass


async def ejecutar_openclaw(job_id: str, prompt: str, limite: int) -> tuple[dict, dict | None]:
    """Ejecuta el job en OpenClaw y devuelve el sobre §5.4 validado.

    Lanza FalloOpenClaw si algo va mal. Nunca devuelve datos inventados ni un
    sobre a medias: o sale el contrato válido, o el job es FALLIDO.
    """
    async with _semaforo:
        # Un job puede haberse cancelado mientras esperaba turno en la cola. Si
        # es así, no se lanza: cancelar tiene que impedir el gasto, no solo
        # interrumpirlo a mitad.
        if _jobs.get(job_id, {}).get("cancelado"):
            raise FalloOpenClaw("Job cancelado antes de arrancar: no se llegó a invocar a OpenClaw.")
        rc, out, err = await _ejecutar_cli(_mensaje(job_id, prompt, limite), job_id)

    # stdout debería ser el envoltorio JSON; si no lo es, aún puede traer el sobre
    # como texto plano (según cómo el agente haya respondido).
    try:
        raiz: object = json.loads(out)
    except json.JSONDecodeError:
        raiz = out

    # Consumo de tokens del agente. Sin esto, TODO el gasto de OpenClaw —que es
    # el grande, dominado por la escritura de caché— era invisible en la app.
    # Se busca ANTES de decidir si el job falló: un job muerto a mitad también
    # gastó, y ese gasto tiene que llegar al libro.
    uso = _localizar_usage(raiz)

    if rc != 0:
        raise FalloOpenClaw(
            f"openclaw agent terminó con código {rc}. stderr: {err.strip()[:600]}", uso=uso
        )

    sobre = _localizar_sobre(raiz)
    if sobre is None:
        raise FalloOpenClaw(
            "La salida de OpenClaw no contiene el JSON del contrato §5.4. "
            f"stdout (primeros 800 car.): {out.strip()[:800] or '(vacío)'} | "
            f"stderr: {err.strip()[:300]}",
            uso=uso,
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
        raise FalloOpenClaw(f"El JSON de OpenClaw no cumple el contrato §5.4: {e}", uso=uso) from e

    return validado.model_dump(), uso


async def _procesar(job_id: str, prompt: str, limite: int) -> None:
    _jobs[job_id]["estado"] = "EN_PROGRESO"
    _guardar_estado()
    try:
        sobre, uso = await ejecutar_openclaw(job_id, prompt, limite)
        _jobs[job_id]["resultado"] = sobre
        _jobs[job_id]["uso"] = uso
        _jobs[job_id]["estado"] = "COMPLETADO"
    except Exception as e:  # noqa: BLE001 — cualquier fallo mata el job, con motivo
        # El gasto ya hecho se anota igual. Un job abortado a mitad consumió
        # tokens reales; dejarlo a cero sería contabilidad falsa.
        uso_parcial = getattr(e, "uso", None)
        if uso_parcial:
            _jobs[job_id]["uso"] = uso_parcial
            _jobs[job_id]["uso_parcial"] = True
        # Cancelado gana sobre fallido: el motivo real es que lo paramos nosotros.
        cancelado = _jobs[job_id].get("cancelado")
        _jobs[job_id]["estado"] = "CANCELADO" if cancelado else "FALLIDO"
        _jobs[job_id]["error"] = str(e)
        print(f"[job {job_id}] {_jobs[job_id]['estado']}: {e}", file=sys.stderr, flush=True)
    finally:
        _jobs[job_id]["finalizado_en"] = datetime.now(timezone.utc).isoformat()
        _guardar_estado()


@app.post("/jobs")
async def crear_job(cuerpo: dict, authorization: str | None = Header(default=None)):
    _auth(authorization)
    job_id = cuerpo.get("job_id") or str(uuid.uuid4())
    _jobs[job_id] = {
        "estado": "PENDIENTE", "resultado": None, "error": None, "uso": None,
        "cancelado": False, "creado_en": datetime.now(timezone.utc).isoformat(),
    }
    _guardar_estado()
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


@app.get("/jobs/{job_id}/uso")
async def uso_job(job_id: str, authorization: str | None = Header(default=None)):
    """Consumo de tokens del job, tal como lo reportó el agente.

    Va aparte del resultado a propósito: el sobre §5.4 tiene `extra="forbid"` y
    meter aquí un campo de telemetría rompería el contrato de extracción.
    Devuelve `{"uso": null}` si el agente no lo reportó — un hueco explícito, no
    un cero inventado.
    """
    _auth(authorization)
    if job_id not in _jobs:
        raise HTTPException(404, "Job desconocido")
    return {
        "job_id": job_id,
        "uso": _jobs[job_id].get("uso"),
        # El consumo de un job abortado es real pero incompleto: el agente pudo
        # gastar más de lo que llegó a imprimir antes de morir.
        "parcial": bool(_jobs[job_id].get("uso_parcial")),
    }


@app.post("/jobs/{job_id}/cancelar")
async def cancelar_job(job_id: str, authorization: str | None = Header(default=None)):
    """Aborta el job DE VERDAD: mata el proceso de OpenClaw y sus hijos.

    Antes esto solo cambiaba una etiqueta en memoria mientras `openclaw agent`
    seguía corriendo. La app decía "cancelado" y el saldo seguía bajando: peor
    que no tener botón, porque daba una falsa sensación de control.
    """
    _auth(authorization)
    j = _jobs.get(job_id)
    if j is None:
        # El adaptador no lo conoce (¿reinicio?). No hay nada que matar aquí, y
        # decirlo permite al backend cerrar el job en vez de sondearlo sin fin.
        raise HTTPException(404, "Job no encontrado: el adaptador no lo tiene en memoria")

    j["cancelado"] = True
    proc = j.get("proc")
    if proc is None:
        # O está en cola esperando turno (el flag impide que arranque), o ya
        # terminó. En ambos casos no hay nada consumiendo tokens ahora mismo.
        en_cola = j["estado"] in _VIVOS
        if en_cola:
            j["estado"] = "CANCELADO"
            j["error"] = "Cancelado antes de arrancar el proceso de OpenClaw."
            j["finalizado_en"] = datetime.now(timezone.utc).isoformat()
        _guardar_estado()
        return {
            "job_id": job_id, "estado": j["estado"], "proceso_abortado": True,
            "detalle": ("estaba en cola: no llegó a invocar a OpenClaw" if en_cola
                        else f"el job ya estaba {j['estado']}: nada que abortar"),
        }

    abortado = await _abortar_proceso(proc)
    # `_procesar` verá el flag y cerrará el job como CANCELADO con su gasto parcial.
    _guardar_estado()
    return {
        "job_id": job_id,
        "estado": "CANCELADO",
        "proceso_abortado": abortado,
        "detalle": (
            "proceso de OpenClaw y sus hijos terminados" if abortado
            else f"AVISO: el proceso NO murió tras SIGKILL ({GRACIA_KILL}s de gracia); "
                 "puede seguir consumiendo tokens. Revísalo a mano en el VPS."
        ),
    }


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
        "jobs_vivos": sum(1 for j in _jobs.values() if j.get("estado") in _VIVOS),
        "estado_persistido": ESTADO_PATH.is_file(),
        "sesiones_legibles": RAIZ_SESIONES.is_dir(),
    }


# --- Sesiones de conversación: el punto ciego del libro de costes ------------
# El libro solo veía lo que pasa por el sistema (analista + jobs). Hablar con el
# agente por terminal o por Telegram gasta igual —y más, porque una sesión larga
# reescribe todo su historial en cada mensaje— y no se anotaba en ninguna parte.
#
# HONESTIDAD SOBRE ESTO: el formato de los .jsonl de sesión de OpenClaw no está
# documentado. Igual que con el envoltorio de `--json`, aquí NO se asume ninguna
# ruta de claves: se busca por FORMA. Si el formato no encaja, la sesión sale con
# tokens a 0 y `formato_reconocido: false` — un hueco visible, nunca un cero que
# se confunda con "no gastó".


def _buscar_texto(nodo: object, claves: set[str], prof: int = 0) -> str | None:
    """Primer valor de texto bajo cualquiera de `claves`, a cualquier profundidad."""
    if prof > 6:
        return None
    if isinstance(nodo, dict):
        for k, v in nodo.items():
            if k in claves and isinstance(v, str) and v:
                return v
        for v in nodo.values():
            if (h := _buscar_texto(v, claves, prof + 1)) is not None:
                return h
    if isinstance(nodo, list):
        for v in nodo:
            if (h := _buscar_texto(v, claves, prof + 1)) is not None:
                return h
    return None


def _leer_sesion(ruta: Path, agente: str) -> dict:
    """Agrega el consumo de un fichero de sesión .jsonl."""
    sumas = {"input": 0, "output": 0, "cacheWrite": 0, "cacheRead": 0}
    turnos = eventos = 0
    ultimo: dict | None = None
    clave_sesion: str | None = None
    modelo: str | None = None
    try:
        with ruta.open(encoding="utf-8", errors="replace") as fh:
            for linea in fh:
                linea = linea.strip()
                if not linea:
                    continue
                eventos += 1
                try:
                    evento = json.loads(linea)
                except json.JSONDecodeError:
                    continue
                clave_sesion = clave_sesion or _buscar_texto(
                    evento, {"sessionKey", "session_key", "sessionId", "session_id"}
                )
                modelo = _buscar_texto(evento, {"model", "modelId", "model_id"}) or modelo
                uso = _localizar_usage(evento)
                if uso:
                    turnos += 1
                    ultimo = uso
                    for k in sumas:
                        with contextlib.suppress(TypeError, ValueError):
                            sumas[k] += int(uso.get(k) or 0)
    except OSError as e:
        return {"id": ruta.stem, "agente": agente, "error": str(e),
                "formato_reconocido": False}

    identidad = clave_sesion or ruta.stem
    # Lo que costará el PRÓXIMO mensaje: es lo que dispara el aviso, no el
    # acumulado. Una sesión de 59 mensajes cobra el historial entero cada vez.
    coste_siguiente = 0
    if ultimo:
        with contextlib.suppress(TypeError, ValueError):
            coste_siguiente = int(ultimo.get("cacheWrite") or 0) + int(ultimo.get("input") or 0)

    return {
        "id": ruta.stem,
        "agente": agente,
        "clave_sesion": clave_sesion,
        "modelo": modelo,
        # Las sesiones de job ya se contabilizan por la vía del job: contarlas
        # aquí otra vez duplicaría el gasto.
        "es_de_job": "inmobiliaria:job:" in identidad or "inmobiliaria-job-" in identidad,
        "eventos": eventos,
        "turnos_facturados": turnos,
        "uso": sumas,
        "tokens_proximo_mensaje": coste_siguiente,
        "formato_reconocido": turnos > 0,
        "bytes": ruta.stat().st_size if ruta.is_file() else 0,
        "modificado_en": datetime.fromtimestamp(
            ruta.stat().st_mtime, timezone.utc
        ).isoformat() if ruta.is_file() else None,
    }


@app.get("/sesiones")
async def listar_sesiones(authorization: str | None = Header(default=None)):
    """Consumo de las sesiones de OpenClaw en disco (conversaciones directas).

    El backend lo consulta periódicamente y anota SOLO el incremento respecto a
    la última lectura, para no contar dos veces la misma sesión.
    """
    _auth(authorization)
    if not RAIZ_SESIONES.is_dir():
        return {
            "raiz": str(RAIZ_SESIONES), "legible": False, "sesiones": [],
            "aviso": (
                f"No existe {RAIZ_SESIONES} o el servicio no puede leerla. El gasto "
                "de las conversaciones directas con el agente NO se está contabilizando. "
                "Ajusta OPENCLAW_SESIONES_PATH o los permisos del servicio."
            ),
        }
    sesiones = []
    for ruta in sorted(RAIZ_SESIONES.glob("*/sessions/*.jsonl")):
        with contextlib.suppress(OSError):
            sesiones.append(_leer_sesion(ruta, ruta.parent.parent.name))
    return {"raiz": str(RAIZ_SESIONES), "legible": True, "sesiones": sesiones}


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
