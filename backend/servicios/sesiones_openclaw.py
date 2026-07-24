"""El punto ciego del libro de costes: las conversaciones directas con el agente.

EL PROBLEMA
-----------
El libro solo veía el gasto que pasa por el sistema: el analista y los jobs de
OpenClaw. Hablar con el agente por terminal (`openclaw agent`) o por Telegram
cuesta exactamente igual —y a menudo más— y no quedaba anotado en ninguna parte.
Medido en real: una sesión de chat con 59 mensajes de historial consumía **76.501
tokens de escritura de caché en UN solo mensaje**. A $2,50 por millón son ~$0,19
cada vez que se escribe, y sube con cada mensaje. Un dashboard que mide una de
las dos fuentes y la llama «gasto total» es peor que no tener dashboard: da
sensación de control.

CÓMO SE RESUELVE
----------------
OpenClaw deja cada sesión en un `.jsonl` con su `usage`. El adaptador (que corre
en el host, donde están esos ficheros) los expone en `GET /sesiones`; aquí se
leen y se anotan con fuente `OPENCLAW_CONVERSACION`, **separada** de los jobs.

DOS CAUTELAS QUE IMPORTAN
-------------------------
1. **El .jsonl acumula.** Cada lectura ve el total de siempre. Se anota solo el
   INCREMENTO respecto a la foto anterior (`sesiones_openclaw`); si no, cada
   pasada del worker sumaría la sesión entera otra vez.
2. **Las sesiones de job NO se cuentan aquí.** Ya entran por la vía del job
   (`--session-key inmobiliaria:job:<id>`). Contarlas dos veces inflaría el
   gasto justo en la cifra que existe para ser fiable.

LO QUE NO ESTÁ VERIFICADO
-------------------------
El formato interno de esos `.jsonl` no está documentado. El adaptador busca el
bloque de consumo **por forma**, no por ruta de claves (igual que con el
envoltorio de `--json`, que ya nos mordió una vez). Si el formato no encaja, la
sesión llega con `formato_reconocido: false` y aquí NO se inventa un cero: se
propaga como hueco y el dashboard avisa del punto ciego. Un cero silencioso se
confundiría con «no gastó».
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ..integraciones.openclaw_client import OpenClawClient
from ..modelos.costes import FuenteUso
from ..nucleo.config import obtener_config
from ..repositorios import configuracion_pais as repo_config
from ..repositorios import sesiones as repo
from . import costes

_CLASES = (
    ("input", "tokens_entrada"),
    ("output", "tokens_salida"),
    ("cacheWrite", "tokens_cache_write"),
    ("cacheRead", "tokens_cache_read"),
)


async def umbral_tokens() -> int:
    """Tokens por mensaje a partir de los cuales una sesión merece limpiarse."""
    valor = await repo_config.obtener_config_app("umbral_tokens_sesion")
    try:
        return int(str(valor))
    except (TypeError, ValueError):
        return 50_000


def _entero(v) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


async def sincronizar() -> dict:
    """Lee las sesiones del adaptador y anota lo nuevo. Idempotente por diseño."""
    cliente = OpenClawClient()
    datos = await cliente.listar_sesiones()
    if datos is None:
        return {
            "legible": False, "sesiones": 0, "nuevas_anotaciones": 0, "coste_usd": "0",
            "aviso": (
                "El adaptador no expone las sesiones (¿versión antigua, o modo manual?). "
                "El gasto de las conversaciones directas con el agente NO se está "
                "contabilizando."
            ),
        }
    if not datos.get("legible", True):
        return {"legible": False, "sesiones": 0, "nuevas_anotaciones": 0,
                "coste_usd": "0", "aviso": datos.get("aviso")}

    cfg = obtener_config()
    anotaciones = 0
    coste_total = Decimal(0)
    sin_formato = 0

    for s in datos.get("sesiones") or []:
        if s.get("es_de_job"):
            continue  # ya contabilizada por la vía del job: no duplicar
        if not s.get("formato_reconocido"):
            sin_formato += 1
            continue

        sesion_id = s.get("clave_sesion") or s.get("id")
        if not sesion_id:
            continue
        uso = s.get("uso") or {}
        previa = await repo.obtener(sesion_id)

        deltas: dict[str, int] = {}
        for clave_api, columna in _CLASES:
            ahora = _entero(uso.get(clave_api))
            antes = _entero(previa.get(columna)) if previa else 0
            # Delta negativo = la sesión se limpió o se rotó. No se anota nada en
            # negativo (sería devolver dinero); se acepta la foto nueva y se sigue.
            deltas[columna] = max(0, ahora - antes)

        modelo = s.get("modelo") or cfg.anthropic_model
        if any(deltas.values()):
            coste_total += await costes.registrar_uso(
                fuente=FuenteUso.OPENCLAW_CONVERSACION,
                modelo=modelo,
                entrada=deltas["tokens_entrada"],
                salida=deltas["tokens_salida"],
                cache_write=deltas["tokens_cache_write"],
                cache_read=deltas["tokens_cache_read"],
                detalle={
                    "origen": "sesion_openclaw",
                    "sesion": sesion_id,
                    "agente": s.get("agente"),
                    "turnos": s.get("turnos_facturados"),
                },
            )
            anotaciones += 1

        await repo.guardar(
            sesion_id=sesion_id,
            agente=s.get("agente"),
            modelo=s.get("modelo"),
            entrada=_entero(uso.get("input")),
            salida=_entero(uso.get("output")),
            cache_write=_entero(uso.get("cacheWrite")),
            cache_read=_entero(uso.get("cacheRead")),
            turnos=_entero(s.get("turnos_facturados")),
            tokens_proximo_mensaje=_entero(s.get("tokens_proximo_mensaje")),
            bytes_=_entero(s.get("bytes")),
            modificada_en=_fecha(s.get("modificado_en")),
        )

    return {
        "legible": True,
        "sesiones": len(datos.get("sesiones") or []),
        "nuevas_anotaciones": anotaciones,
        "coste_usd": str(coste_total),
        "sin_formato_reconocido": sin_formato,
    }


def _fecha(valor):
    if not valor:
        return None
    try:
        return datetime.fromisoformat(str(valor))
    except ValueError:
        return None


async def estado() -> dict:
    """Lo que la pantalla de Costes necesita saber del punto ciego.

    Devuelve las sesiones conocidas y cuáles pasan del umbral. `contabilizado`
    dice si el gasto de conversación está entrando de verdad en el libro: si es
    False, el dashboard tiene que decir que «gasto total» no significa «todo lo
    que gasto».
    """
    umbral = await umbral_tokens()
    filas = await repo.listar()
    for f in filas:
        f["supera_umbral"] = _entero(f.get("tokens_proximo_mensaje")) >= umbral
    return {
        "umbral_tokens_sesion": umbral,
        "contabilizado": bool(filas),
        "sesiones": filas,
        "sesiones_a_limpiar": [f for f in filas if f["supera_umbral"]],
    }
