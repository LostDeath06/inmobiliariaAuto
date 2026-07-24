"""Cliente HTTP para OpenClaw (§5.3).

OpenClaw YA EXISTE (agente externo en un VPS). Aquí NO se construye ningún scraper:
solo se habla con él por HTTP. Soporta dos modos:
- http:   producción, llama al VPS 24/7.
- manual: desarrollo, el prompt se muestra en la UI y el JSON de vuelta se pega.

Resiliencia: timeouts, reintentos con backoff exponencial + jitter y un circuit
breaker que se abre si OpenClaw cae. Un job nunca se queda colgado.
"""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass

import httpx

from ..modelos.openclaw import SobreScraping
from ..nucleo.config import obtener_config


class OpenClawError(Exception):
    """Fallo al hablar con OpenClaw."""


class CircuitoAbierto(OpenClawError):
    """El circuit breaker está abierto: OpenClaw se considera caído."""


class JobDesconocido(OpenClawError):
    """El adaptador respondió 404: no tiene ese job.

    Es un error DISTINTO de "OpenClaw no responde", y por eso tiene su propio
    tipo. Un 404 no se arregla reintentando: el adaptador guarda los jobs en
    memoria y, si se reinició, ese job ya no existe para él. Tratarlo como un
    fallo de red cualquiera es lo que dejaba al backend sondeando un job muerto
    cada 3 segundos para siempre.
    """


@dataclass
class JobScraping:
    job_id: str
    prompt: str
    limite_anuncios: int


class _CircuitBreaker:
    def __init__(self, umbral_fallos: int = 5, enfriamiento_seg: float = 60.0):
        self.umbral_fallos = umbral_fallos
        self.enfriamiento_seg = enfriamiento_seg
        self._fallos = 0
        self._abierto_hasta = 0.0

    def permitir(self) -> bool:
        if self._fallos < self.umbral_fallos:
            return True
        return time.monotonic() >= self._abierto_hasta

    def registrar_exito(self) -> None:
        self._fallos = 0
        self._abierto_hasta = 0.0

    def registrar_fallo(self) -> None:
        self._fallos += 1
        if self._fallos >= self.umbral_fallos:
            self._abierto_hasta = time.monotonic() + self.enfriamiento_seg


class OpenClawClient:
    def __init__(self):
        cfg = obtener_config()
        self.modo = cfg.openclaw_mode
        self.base_url = cfg.openclaw_base_url.rstrip("/")
        self.api_key = cfg.openclaw_api_key
        self.timeout = cfg.openclaw_timeout_segundos
        self.max_reintentos = cfg.openclaw_max_reintentos
        self._breaker = _CircuitBreaker()

    def _cabeceras(self) -> dict:
        cab = {"Content-Type": "application/json"}
        if self.api_key:
            cab["Authorization"] = f"Bearer {self.api_key}"
        return cab

    async def _peticion(self, metodo: str, ruta: str, **kwargs) -> httpx.Response:
        if not self._breaker.permitir():
            raise CircuitoAbierto("OpenClaw no disponible (circuit breaker abierto)")
        ultimo_error: Exception | None = None
        for intento in range(self.max_reintentos + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as cliente:
                    resp = await cliente.request(
                        metodo, f"{self.base_url}{ruta}", headers=self._cabeceras(), **kwargs
                    )
                # Un 404 es una respuesta, no una caída: el adaptador está vivo y
                # dice que no conoce el recurso. Reintentarlo tres veces con
                # backoff era gastar segundos para oír lo mismo, y encima abría
                # el circuit breaker contra un servicio que funciona.
                if resp.status_code == 404:
                    self._breaker.registrar_exito()
                    raise JobDesconocido(f"El adaptador no reconoce {ruta} (404)")
                resp.raise_for_status()
                self._breaker.registrar_exito()
                return resp
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                ultimo_error = e
                self._breaker.registrar_fallo()
                if intento < self.max_reintentos:
                    # backoff exponencial + jitter
                    espera = min(2 ** intento, 30) + random.uniform(0, 1)
                    await asyncio.sleep(espera)
        raise OpenClawError(f"OpenClaw falló tras {self.max_reintentos + 1} intentos: {ultimo_error}")

    async def enviar_job(self, job: JobScraping) -> str:
        """Envía un job. Devuelve el openclaw_job_id. En modo manual no aplica."""
        if self.modo == "manual":
            raise OpenClawError(
                "Modo manual: el prompt se copia desde la UI y el JSON se pega de vuelta."
            )
        resp = await self._peticion(
            "POST", "/jobs",
            json={"job_id": job.job_id, "prompt": job.prompt,
                  "limite_anuncios": job.limite_anuncios},
        )
        return resp.json().get("job_id", job.job_id)

    async def consultar_job(self, openclaw_job_id: str) -> dict:
        """Estado y motivo, tal como los da el adaptador. Lanza JobDesconocido si 404."""
        if self.modo == "manual":
            raise OpenClawError("Modo manual: sin consulta de estado remota.")
        resp = await self._peticion("GET", f"/jobs/{openclaw_job_id}")
        return resp.json() or {}

    async def consultar_estado(self, openclaw_job_id: str) -> str:
        return (await self.consultar_job(openclaw_job_id)).get("estado", "DESCONOCIDO")

    async def obtener_resultado(self, openclaw_job_id: str) -> SobreScraping:
        if self.modo == "manual":
            raise OpenClawError("Modo manual: el JSON se pega por la UI.")
        resp = await self._peticion("GET", f"/jobs/{openclaw_job_id}/resultado")
        # Valida contra el contrato §5.4 (o lanza).
        return SobreScraping.model_validate(resp.json())

    async def obtener_uso(self, openclaw_job_id: str) -> tuple[dict | None, bool]:
        """Consumo de tokens del job que reporta el agente (meta.agentMeta.usage).

        Devuelve (uso, parcial). `parcial` es True cuando el job murió a mitad
        (cancelado o fallido): lo gastado es real pero incompleto.

        Nunca hace fallar el job: el gasto es telemetría. Si el agente no lo
        reporta o el endpoint no existe, devuelve (None, False) y el dashboard lo
        marca como hueco en vez de inventar un cero.
        """
        if self.modo == "manual":
            return None, False
        try:
            resp = await self._peticion("GET", f"/jobs/{openclaw_job_id}/uso")
            cuerpo = resp.json() or {}
            return cuerpo.get("uso"), bool(cuerpo.get("parcial"))
        except Exception:  # noqa: BLE001
            return None, False

    async def cancelar_job(self, openclaw_job_id: str) -> dict:
        """Pide el aborto y devuelve lo que dice el adaptador.

        NO se resume a un booleano: importa distinguir "proceso muerto" de "el
        adaptador dice CANCELADO pero el proceso sigue vivo". Lo segundo hay que
        contarlo, no esconderlo detrás de un `False` ambiguo.
        """
        if self.modo == "manual":
            return {"proceso_abortado": True, "detalle": "modo manual: no hay proceso remoto"}
        try:
            resp = await self._peticion("POST", f"/jobs/{openclaw_job_id}/cancelar")
            return resp.json() or {}
        except JobDesconocido:
            return {
                "proceso_abortado": True,
                "detalle": "el adaptador no reconoce el job (¿reinicio?): no hay proceso que abortar",
                "desconocido": True,
            }
        except OpenClawError as e:
            return {"proceso_abortado": False, "detalle": f"no se pudo contactar con el adaptador: {e}"}

    async def listar_sesiones(self) -> dict | None:
        """Sesiones de OpenClaw en disco, con su consumo (§ punto ciego).

        Telemetría: si el adaptador no lo expone o falla, devuelve None y el
        dashboard muestra el punto ciego sin cifras en vez de fingir que no
        existe gasto fuera del sistema.
        """
        if self.modo == "manual":
            return None
        try:
            resp = await self._peticion("GET", "/sesiones")
            return resp.json() or {}
        except Exception:  # noqa: BLE001
            return None

    async def health(self) -> bool:
        if self.modo == "manual":
            return True
        try:
            resp = await self._peticion("GET", "/health")
            return resp.status_code == 200
        except OpenClawError:
            return False
