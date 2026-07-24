"""Cancelar tiene que MATAR el proceso, no cambiar una etiqueta.

Por qué existe este fichero. La versión anterior de `POST /jobs/{id}/cancelar`
del adaptador hacía exactamente esto:

    _jobs[job_id]["estado"] = "CANCELADO"

...y nada más. El subproceso `openclaw agent` seguía vivo. La app decía
"CANCELADO" mientras el saldo bajaba. Eso es peor que no tener botón: un fallo
silencioso que además da sensación de control (Principio 3).

Lo que se protege aquí:
1. `_abortar_proceso` mata el proceso Y sus hijos, de verdad, y lo demuestra
   contra procesos reales.
2. Un job cancelado deja su gasto anotado: lo consumido hasta el corte es real.
3. Si el proceso NO muere, se dice. Nunca un "CANCELADO" limpio encima de un
   agente que sigue gastando.
4. No se puede cancelar lo que ya terminó.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from backend.modelos.enumeraciones import EstadoJob
from backend.modelos.pipeline import Job
from backend.servicios import despacho


def _cargar_adaptador():
    """El adaptador vive en scripts/ y no es un paquete: se carga por ruta."""
    ruta = Path(__file__).resolve().parents[2] / "scripts" / "adaptador_openclaw_vps.py"
    spec = importlib.util.spec_from_file_location("adaptador_openclaw_vps", ruta)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["adaptador_openclaw_vps"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


adaptador = _cargar_adaptador()


# --- 1. El proceso muere de verdad ------------------------------------------


@pytest.mark.asyncio
async def test_abortar_mata_un_proceso_vivo():
    """El caso literal del bug: un proceso que no piensa terminar solo."""
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-c", "import time; time.sleep(120)",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        start_new_session=(os.name == "posix"),
    )
    assert proc.returncode is None  # vivo antes de abortar

    abortado = await adaptador._abortar_proceso(proc)

    assert abortado is True
    assert proc.returncode is not None, "el proceso seguía vivo tras cancelar"


@pytest.mark.asyncio
async def test_abortar_un_proceso_que_ignora_sigterm():
    """SIGTERM ignorado → SIGKILL. Un agente colgado no negocia su muerte."""
    if os.name != "posix":
        pytest.skip("SIGTERM/SIGKILL solo aplica en el VPS (POSIX)")
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-c",
        "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(120)",
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        start_new_session=True,
    )
    adaptador.GRACIA_KILL = 1.0  # no esperar 5 s en un test
    assert await adaptador._abortar_proceso(proc) is True
    assert proc.returncode is not None


@pytest.mark.asyncio
async def test_abortar_un_proceso_ya_muerto_no_falla():
    proc = await asyncio.create_subprocess_exec(sys.executable, "-c", "pass")
    await proc.wait()
    assert await adaptador._abortar_proceso(proc) is True


# --- 2 a 4. El flujo de cancelación del backend ------------------------------


class _ClienteFalso:
    """Adaptador de mentira: dice si abortó y cuánto se gastó hasta el corte."""

    def __init__(self, *, abortado=True, uso=None, parcial=True):
        self.respuesta = {
            "proceso_abortado": abortado,
            "detalle": "proceso terminado" if abortado else "el proceso NO murió",
        }
        self._uso = uso
        self._parcial = parcial
        self.cancelado_con = None

    async def cancelar_job(self, oc_id):
        self.cancelado_con = oc_id
        return self.respuesta

    async def obtener_uso(self, oc_id):
        return self._uso, self._parcial


@pytest.fixture
def entorno(monkeypatch):
    """Sustituye BD y adaptador. Devuelve el estado observable del test."""
    estado = {"job": None, "cerrado": None, "usos": []}

    async def obtener(job_id):
        return estado["job"]

    async def cerrar(job_id, est, motivo):
        estado["cerrado"] = (est, motivo)
        return estado["job"]

    async def registrar_uso(**kw):
        estado["usos"].append(kw)
        return Decimal("0.0421")

    monkeypatch.setattr(despacho.repo_jobs, "obtener", obtener)
    monkeypatch.setattr(despacho.repo_jobs, "cerrar", cerrar)
    monkeypatch.setattr(despacho.costes, "registrar_uso", registrar_uso)
    return estado


def _job(estado: EstadoJob, oc_id: str | None = "oc-1") -> Job:
    return Job(id=uuid4(), busqueda_id=uuid4(), estado=estado, openclaw_job_id=oc_id)


@pytest.mark.asyncio
async def test_cancelar_anota_el_gasto_parcial(entorno, monkeypatch):
    """Un job cancelado a mitad YA consumió tokens: tienen que llegar al libro.

    Dejarlo a cero sería contabilidad falsa justo donde más se mira el número.
    """
    entorno["job"] = _job(EstadoJob.EN_PROGRESO)
    cliente = _ClienteFalso(uso={"input": 1200, "output": 300, "cacheWrite": 19254, "cacheRead": 0})
    monkeypatch.setattr(despacho, "OpenClawClient", lambda: cliente)

    r = await despacho.cancelar_job(entorno["job"].id)

    assert r["proceso_abortado"] is True
    assert entorno["cerrado"][0] == "CANCELADO"
    assert len(entorno["usos"]) == 1, "el gasto del job cancelado no se anotó"
    uso = entorno["usos"][0]
    assert uso["cache_write"] == 19254  # la partida grande, la que se ignoraba
    assert uso["detalle"]["parcial"] is True
    # El aviso admite que la cifra puede quedarse corta: el agente pudo gastar
    # más de lo que alcanzó a reportar antes de morir. Un dato honesto sobre su
    # propia incertidumbre, no una cifra presentada como exacta.
    assert "puede ser algo mayor" in uso["detalle"]["aviso_parcial"]


@pytest.mark.asyncio
async def test_si_el_proceso_no_muere_el_motivo_lo_dice(entorno, monkeypatch):
    """Principio 3: el peor resultado es un CANCELADO tranquilo sobre un agente vivo."""
    entorno["job"] = _job(EstadoJob.EN_PROGRESO)
    monkeypatch.setattr(despacho, "OpenClawClient", lambda: _ClienteFalso(abortado=False))

    r = await despacho.cancelar_job(entorno["job"].id)

    assert r["proceso_abortado"] is False
    estado, motivo = entorno["cerrado"]
    assert estado == "CANCELADO"
    assert "AVISO" in motivo
    assert "seguir consumiendo" in motivo


@pytest.mark.asyncio
async def test_no_se_cancela_un_job_ya_terminado(entorno, monkeypatch):
    entorno["job"] = _job(EstadoJob.COMPLETADO)
    monkeypatch.setattr(despacho, "OpenClawClient", lambda: _ClienteFalso())

    with pytest.raises(despacho.EstadoNoCancelable):
        await despacho.cancelar_job(entorno["job"].id)

    assert entorno["cerrado"] is None, "un job terminado no debe reescribirse"


@pytest.mark.asyncio
async def test_los_tres_estados_vivos_son_cancelables():
    """Los que pide el propietario: PENDIENTE, ENVIADO y EN_PROGRESO."""
    assert despacho.CANCELABLES == {
        EstadoJob.PENDIENTE, EstadoJob.ENVIADO, EstadoJob.EN_PROGRESO,
    }


@pytest.mark.asyncio
async def test_cancelar_un_job_sin_openclaw_id_no_llama_al_adaptador(entorno, monkeypatch):
    """PENDIENTE que aún no salió del backend: no hay proceso remoto que matar."""
    entorno["job"] = _job(EstadoJob.PENDIENTE, oc_id=None)
    cliente = _ClienteFalso()
    monkeypatch.setattr(despacho, "OpenClawClient", lambda: cliente)

    r = await despacho.cancelar_job(entorno["job"].id)

    assert r["proceso_abortado"] is True
    assert cliente.cancelado_con is None
    assert entorno["usos"] == []
