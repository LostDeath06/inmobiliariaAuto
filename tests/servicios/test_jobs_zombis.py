"""Ningún job puede quedarse EN_PROGRESO para siempre.

El caso real: tras `systemctl restart openclaw-adaptador`, el backend seguía
sondeando un job antiguo cada pocos segundos y el adaptador contestaba
`404 Not Found` indefinidamente. El adaptador guarda los jobs en memoria
(`_jobs: dict`), así que al reiniciarse los pierde; el backend, que lo tenía como
EN_PROGRESO, no tenía ningún camino que llevara a cerrarlo.

Lo que se protege aquí:
1. Un 404 NO es un fallo de red: no se reintenta y tiene su propio tipo. Antes se
   reintentaba tres veces con backoff para oír lo mismo.
2. Tras N consultas seguidas con 404, el job se cierra FALLIDO con el motivo.
3. El contador es de 404 SEGUIDOS: una respuesta buena lo devuelve a cero.
4. Existe un timeout duro por job, y se aplica aunque el adaptador no conteste
   nunca. Es la red que garantiza que la espera acaba siempre.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest

from backend.integraciones.openclaw_client import JobDesconocido, OpenClawClient
from backend.modelos.enumeraciones import EstadoJob
from backend.modelos.pipeline import Job
from backend.worker import worker


def _job(**kw) -> Job:
    base = dict(
        id=uuid4(), busqueda_id=uuid4(), estado=EstadoJob.EN_PROGRESO,
        openclaw_job_id="oc-1", iniciado_en=datetime.now(timezone.utc),
    )
    return Job(**{**base, **kw})


# --- 1. Un 404 no se reintenta ----------------------------------------------


@pytest.mark.asyncio
async def test_un_404_no_se_reintenta_y_tiene_tipo_propio(monkeypatch):
    """Reintentar un 404 es gastar segundos para oír lo mismo, y encima abría el
    circuit breaker contra un adaptador que funciona perfectamente."""
    llamadas = {"n": 0}

    class _Respuesta:
        status_code = 404
        def json(self): return {}
        def raise_for_status(self): raise AssertionError("no debería llegar aquí")

    class _Cliente:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def request(self, *a, **k):
            llamadas["n"] += 1
            return _Respuesta()

    monkeypatch.setattr(httpx, "AsyncClient", _Cliente)
    cliente = OpenClawClient()
    cliente.modo = "http"

    with pytest.raises(JobDesconocido):
        await cliente.consultar_estado("oc-1")

    assert llamadas["n"] == 1, "un 404 se reintentó: es una respuesta, no una caída"


# --- 2 y 3. Rendirse ante el 404 persistente --------------------------------


@pytest.fixture
def worker_falso(monkeypatch):
    """Aísla el worker de la BD y del adaptador."""
    estado = {"jobs": [], "cerrados": [], "contador": 0, "reinicios": 0, "estado_remoto": None,
              "excepcion": None}

    async def listar_vivos():
        return estado["jobs"]

    async def cerrar(job_id, est, motivo):
        estado["cerrados"].append((job_id, est, motivo))
        estado["jobs"] = [j for j in estado["jobs"] if j.id != job_id]
        return None

    async def contar(job_id):
        estado["contador"] += 1
        return estado["contador"]

    async def reiniciar(job_id):
        estado["reinicios"] += 1

    async def limite(clave, por_defecto):
        return {"max_sondeos_no_encontrado": 3, "margen_timeout_job_segundos": 120}[clave]

    class _Cliente:
        async def consultar_estado(self, oc_id):
            if estado["excepcion"]:
                raise estado["excepcion"]
            return estado["estado_remoto"]

    monkeypatch.setattr(worker.repo_jobs, "listar_vivos", listar_vivos)
    monkeypatch.setattr(worker.repo_jobs, "cerrar", cerrar)
    monkeypatch.setattr(worker.repo_jobs, "contar_sondeo_no_encontrado", contar)
    monkeypatch.setattr(worker.repo_jobs, "reiniciar_sondeo_no_encontrado", reiniciar)
    monkeypatch.setattr(worker, "_limite", limite)
    monkeypatch.setattr(worker, "OpenClawClient", lambda: _Cliente())
    monkeypatch.setattr(
        worker.obtener_config(), "openclaw_mode", "http", raising=False
    )
    return estado


@pytest.mark.asyncio
async def test_tras_varios_404_seguidos_el_job_se_cierra(worker_falso):
    """El caso del enunciado: el adaptador se reinició y no reconoce el job."""
    worker_falso["jobs"] = [_job()]
    worker_falso["excepcion"] = JobDesconocido("404")

    # Dos primeras consultas: se le dan oportunidades por si es un arranque a medias.
    await worker._procesar_jobs_http()
    await worker._procesar_jobs_http()
    assert worker_falso["cerrados"] == [], "se rindió demasiado pronto"

    # La tercera alcanza el límite configurado.
    await worker._procesar_jobs_http()

    assert len(worker_falso["cerrados"]) == 1
    _, est, motivo = worker_falso["cerrados"][0]
    assert est == "FALLIDO"
    assert "no reconoce el job" in motivo and "reinicio" in motivo
    assert "Se deja de consultar" in motivo


@pytest.mark.asyncio
async def test_una_respuesta_buena_devuelve_el_contador_a_cero(worker_falso):
    """Son 404 SEGUIDOS. Un reinicio entre dos jobs sanos no debe acercar al
    siguiente a la muerte."""
    worker_falso["jobs"] = [_job()]
    worker_falso["estado_remoto"] = "EN_PROGRESO"

    await worker._procesar_jobs_http()

    assert worker_falso["reinicios"] == 1
    assert worker_falso["cerrados"] == []


# --- 4. El timeout duro ------------------------------------------------------


@pytest.mark.asyncio
async def test_timeout_duro_cierra_el_job_sin_preguntar(worker_falso):
    """La garantía de fondo: aunque el adaptador no conteste NUNCA, la espera
    termina. `OPENCLAW_TIMEOUT_SEGUNDOS` existía pero no se aplicaba al job."""
    cfg = worker.obtener_config()
    viejo = datetime.now(timezone.utc) - timedelta(
        seconds=cfg.openclaw_timeout_segundos + 60 + 120 + 30
    )
    worker_falso["jobs"] = [_job(iniciado_en=viejo)]
    # Que quede claro que no depende de la respuesta del adaptador:
    worker_falso["excepcion"] = AssertionError("no se debe consultar un job vencido")

    await worker._procesar_jobs_http()

    assert len(worker_falso["cerrados"]) == 1
    _, est, motivo = worker_falso["cerrados"][0]
    assert est == "FALLIDO"
    assert "Timeout duro" in motivo
    assert "para siempre" in motivo


@pytest.mark.asyncio
async def test_un_job_reciente_no_se_cierra_por_timeout(worker_falso):
    worker_falso["jobs"] = [_job(iniciado_en=datetime.now(timezone.utc) - timedelta(minutes=2))]
    worker_falso["estado_remoto"] = "EN_PROGRESO"

    await worker._procesar_jobs_http()

    assert worker_falso["cerrados"] == []


@pytest.mark.asyncio
async def test_el_timeout_usa_created_at_si_no_hay_iniciado_en(worker_falso):
    """Los jobs anteriores a este cambio no tienen `iniciado_en`. Sin respaldo se
    quedarían fuera del timeout justo los que ya están colgados."""
    cfg = worker.obtener_config()
    viejo = datetime.now(timezone.utc) - timedelta(seconds=cfg.openclaw_timeout_segundos + 3600)
    worker_falso["jobs"] = [_job(iniciado_en=None, created_at=viejo)]
    worker_falso["excepcion"] = AssertionError("no se debe consultar un job vencido")

    await worker._procesar_jobs_http()

    assert len(worker_falso["cerrados"]) == 1
    assert worker_falso["cerrados"][0][1] == "FALLIDO"
