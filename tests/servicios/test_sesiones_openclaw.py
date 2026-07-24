"""El punto ciego: el gasto de hablar con el agente fuera del sistema.

El libro solo veía el analista y los jobs. Las conversaciones directas
(`openclaw agent` por terminal, o Telegram) cuestan igual y no se anotaban en
ninguna parte. Medido en real: una sesión con 59 mensajes de historial consumía
**76.501 tokens de cacheWrite en UN mensaje**, porque arrastra todo el historial.

Lo que se protege aquí, que es donde esto se puede romper de forma cara:
1. **No contar dos veces.** El .jsonl ACUMULA: cada lectura ve el total, no lo
   nuevo. Sin restar la foto anterior, cada pasada del worker sumaría la sesión
   entera otra vez y el gasto se multiplicaría por el número de lecturas.
2. **No contar los jobs dos veces.** Las sesiones `inmobiliaria:job:*` ya entran
   por la vía del job.
3. **Limpiar una sesión no genera un apunte negativo.** Si el fichero encoge, se
   acepta la foto nueva y se sigue: nadie devuelve dinero.
4. **Un formato que no se reconoce es un hueco, no un cero.** Un cero silencioso
   se confundiría con "no gastó" (Principio 3).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from backend.modelos.costes import FuenteUso
from backend.servicios import sesiones_openclaw as srv


@pytest.fixture
def entorno(monkeypatch):
    """Adaptador y BD de mentira. `fotos` hace de tabla `sesiones_openclaw`."""
    estado = {"respuesta": None, "fotos": {}, "usos": []}

    class _Cliente:
        async def listar_sesiones(self):
            return estado["respuesta"]

    async def obtener(sesion_id):
        return estado["fotos"].get(sesion_id)

    async def guardar(*, sesion_id, entrada, salida, cache_write, cache_read, **kw):
        estado["fotos"][sesion_id] = {
            "tokens_entrada": entrada, "tokens_salida": salida,
            "tokens_cache_write": cache_write, "tokens_cache_read": cache_read,
        }

    async def registrar_uso(**kw):
        estado["usos"].append(kw)
        return Decimal("0.1913")

    monkeypatch.setattr(srv, "OpenClawClient", lambda: _Cliente())
    monkeypatch.setattr(srv.repo, "obtener", obtener)
    monkeypatch.setattr(srv.repo, "guardar", guardar)
    monkeypatch.setattr(srv.costes, "registrar_uso", registrar_uso)
    return estado


def _sesion(**kw) -> dict:
    """La sesión medida de verdad: 59 mensajes, 76.501 de cacheWrite el último."""
    base = {
        "id": "agent-main-main", "clave_sesion": "agent:main:main", "agente": "main",
        "modelo": "claude-sonnet-5", "es_de_job": False, "formato_reconocido": True,
        "turnos_facturados": 59, "tokens_proximo_mensaje": 76_501, "bytes": 412_000,
        "modificado_en": "2026-07-24T10:00:00+00:00",
        "uso": {"input": 4_000, "output": 2_500, "cacheWrite": 900_000, "cacheRead": 120_000},
    }
    return {**base, **kw}


@pytest.mark.asyncio
async def test_la_primera_lectura_anota_todo_el_consumo(entorno):
    entorno["respuesta"] = {"legible": True, "sesiones": [_sesion()]}

    r = await srv.sincronizar()

    assert r["nuevas_anotaciones"] == 1
    uso = entorno["usos"][0]
    assert uso["fuente"] is FuenteUso.OPENCLAW_CONVERSACION  # separada de los jobs
    assert uso["cache_write"] == 900_000
    assert uso["detalle"]["sesion"] == "agent:main:main"


@pytest.mark.asyncio
async def test_releer_sin_cambios_no_anota_nada(entorno):
    """El fallo caro si esto se hiciera mal: el worker lee cada 5 minutos. Sumar
    el total en cada pasada multiplicaría el gasto por 288 al día."""
    entorno["respuesta"] = {"legible": True, "sesiones": [_sesion()]}

    await srv.sincronizar()
    await srv.sincronizar()
    await srv.sincronizar()

    assert len(entorno["usos"]) == 1, "se contó la misma sesión más de una vez"


@pytest.mark.asyncio
async def test_solo_se_anota_el_incremento(entorno):
    """Un mensaje nuevo de 76.501 de cacheWrite: eso, y solo eso, es lo nuevo."""
    entorno["respuesta"] = {"legible": True, "sesiones": [_sesion()]}
    await srv.sincronizar()

    crecida = _sesion(uso={"input": 4_300, "output": 2_700, "cacheWrite": 976_501, "cacheRead": 120_000})
    entorno["respuesta"] = {"legible": True, "sesiones": [crecida]}
    await srv.sincronizar()

    assert len(entorno["usos"]) == 2
    delta = entorno["usos"][1]
    assert delta["cache_write"] == 76_501
    assert delta["entrada"] == 300
    assert delta["salida"] == 200
    assert delta["cache_read"] == 0


@pytest.mark.asyncio
async def test_las_sesiones_de_job_no_se_cuentan_aqui(entorno):
    """Ya entran como gasto del job. Contarlas dos veces inflaría el total justo
    en la cifra que existe para ser fiable."""
    entorno["respuesta"] = {"legible": True, "sesiones": [
        _sesion(id="inmobiliaria:job:abc", clave_sesion="inmobiliaria:job:abc", es_de_job=True),
    ]}

    r = await srv.sincronizar()

    assert r["nuevas_anotaciones"] == 0
    assert entorno["usos"] == []


@pytest.mark.asyncio
async def test_limpiar_una_sesion_no_genera_un_apunte_negativo(entorno):
    """Al limpiar, el fichero encoge. El delta sale negativo y NO se anota:
    nadie devuelve dinero. Se acepta la foto nueva y se sigue contando desde ahí."""
    entorno["respuesta"] = {"legible": True, "sesiones": [_sesion()]}
    await srv.sincronizar()

    limpia = _sesion(uso={"input": 100, "output": 50, "cacheWrite": 2_000, "cacheRead": 0},
                     turnos_facturados=1, tokens_proximo_mensaje=2_100)
    entorno["respuesta"] = {"legible": True, "sesiones": [limpia]}
    await srv.sincronizar()

    assert len(entorno["usos"]) == 1, "la limpieza generó un apunte"

    # Y desde la foto nueva se vuelve a contar bien, sin arrastrar el pasado.
    entorno["respuesta"] = {"legible": True, "sesiones": [
        _sesion(uso={"input": 150, "output": 50, "cacheWrite": 5_000, "cacheRead": 0})
    ]}
    await srv.sincronizar()
    assert entorno["usos"][-1]["cache_write"] == 3_000


@pytest.mark.asyncio
async def test_un_formato_no_reconocido_es_un_hueco_no_un_cero(entorno):
    """El formato de los .jsonl no está documentado. Si no encaja, se dice: un 0
    silencioso se leería como «esta sesión no gastó»."""
    entorno["respuesta"] = {"legible": True, "sesiones": [_sesion(formato_reconocido=False)]}

    r = await srv.sincronizar()

    assert r["sin_formato_reconocido"] == 1
    assert entorno["usos"] == []


@pytest.mark.asyncio
async def test_si_no_se_pueden_leer_las_sesiones_se_dice(entorno):
    """El caso que dispara el aviso del dashboard: sin esto, «gasto total»
    seguiría presentándose como si fuera todo el gasto."""
    entorno["respuesta"] = None

    r = await srv.sincronizar()

    assert r["legible"] is False
    assert "NO se está contabilizando" in r["aviso"]


# --- El lector del .jsonl (adaptador) ---------------------------------------
# El formato de estos ficheros NO está documentado, así que el lector busca el
# bloque de consumo POR FORMA y no por ruta de claves. Estos tests fijan ese
# contrato: encontrar el `usage` esté donde esté, y admitir que no lo encuentra
# cuando de verdad no está.


def _adaptador():
    import importlib.util
    import sys
    from pathlib import Path
    ruta = Path(__file__).resolve().parents[2] / "scripts" / "adaptador_openclaw_vps.py"
    spec = importlib.util.spec_from_file_location("adaptador_openclaw_vps", ruta)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["adaptador_openclaw_vps"] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def test_el_lector_encuentra_el_usage_este_donde_este(tmp_path):
    """Tres anidamientos distintos en el mismo fichero: los tres cuentan."""
    ad = _adaptador()
    fichero = tmp_path / "agent-main-main.jsonl"
    fichero.write_text(
        '{"role":"user","content":"hola"}\n'
        '{"role":"assistant","model":"claude-sonnet-5",'
        '"usage":{"input":100,"output":50,"cacheWrite":19000,"cacheRead":0}}\n'
        '{"role":"assistant","meta":{"agentMeta":'
        '{"usage":{"input":120,"output":60,"cacheWrite":40000,"cacheRead":19000}}}}\n'
        '{"sessionKey":"agent:main:main"}\n'
        '{"role":"assistant","message":{"usage":'
        '{"input":140,"output":70,"cacheWrite":76501,"cacheRead":59000}}}\n',
        encoding="utf-8",
    )

    s = ad._leer_sesion(fichero, "main")

    assert s["formato_reconocido"] is True
    assert s["turnos_facturados"] == 3
    assert s["uso"]["cacheWrite"] == 19000 + 40000 + 76501
    assert s["clave_sesion"] == "agent:main:main"
    assert s["modelo"] == "claude-sonnet-5"
    # Lo que costará el PRÓXIMO mensaje: el último turno, no el acumulado.
    assert s["tokens_proximo_mensaje"] == 76501 + 140
    assert s["es_de_job"] is False


def test_el_lector_reconoce_una_sesion_de_job(tmp_path):
    """Las de job no se contabilizan aquí: ya entran por la vía del job."""
    ad = _adaptador()
    fichero = tmp_path / "inmobiliaria-job-abc.jsonl"
    fichero.write_text(
        '{"sessionKey":"inmobiliaria:job:abc",'
        '"usage":{"input":10,"output":5,"cacheWrite":100,"cacheRead":0}}\n',
        encoding="utf-8",
    )

    assert ad._leer_sesion(fichero, "main")["es_de_job"] is True


def test_un_formato_desconocido_no_finge_un_cero(tmp_path):
    """Si el .jsonl no trae nada con forma de consumo, se dice. Un 0 silencioso
    se leería como «esta sesión no gastó», que es justo lo contrario."""
    ad = _adaptador()
    fichero = tmp_path / "raro.jsonl"
    fichero.write_text('{"algo":"que no es un usage"}\nno-es-json\n', encoding="utf-8")

    s = ad._leer_sesion(fichero, "main")

    assert s["formato_reconocido"] is False
    assert s["turnos_facturados"] == 0
    assert s["eventos"] == 2  # sí vio líneas: el fichero existe y se leyó
