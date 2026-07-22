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

    async def consultar_estado(self, openclaw_job_id: str) -> str:
        if self.modo == "manual":
            raise OpenClawError("Modo manual: sin consulta de estado remota.")
        resp = await self._peticion("GET", f"/jobs/{openclaw_job_id}")
        return resp.json().get("estado", "DESCONOCIDO")

    async def obtener_resultado(self, openclaw_job_id: str) -> SobreScraping:
        if self.modo == "manual":
            raise OpenClawError("Modo manual: el JSON se pega por la UI.")
        resp = await self._peticion("GET", f"/jobs/{openclaw_job_id}/resultado")
        # Valida contra el contrato §5.4 (o lanza).
        return SobreScraping.model_validate(resp.json())

    async def cancelar_job(self, openclaw_job_id: str) -> bool:
        if self.modo == "manual":
            return True
        try:
            await self._peticion("POST", f"/jobs/{openclaw_job_id}/cancelar")
            return True
        except OpenClawError:
            return False

    async def health(self) -> bool:
        if self.modo == "manual":
            return True
        try:
            resp = await self._peticion("GET", "/health")
            return resp.status_code == 200
        except OpenClawError:
            return False
