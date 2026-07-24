"""Analista cualitativo (Claude API).

PRINCIPIO 1: Claude SOLO emite juicio cualitativo estructurado (enums, booleanos,
categorías, texto corto). CERO números calculados. El motor financiero (Python)
hace todas las cifras.

Salida forzada a JSON estricto validado con Pydantic (AnalisisCualitativo).
Reintentos si el JSON no valida (máx. 2); luego marca el inmueble como
ANALISIS_FALLIDO y continúa (nunca aborta el lote). Cacheado por hash_contenido.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from ..modelos.analisis import AnalisisCualitativo
from ..modelos.pipeline import Inmueble
from ..nucleo.config import obtener_config

# El system prompt DEBE contener textualmente esta prohibición (§8.3).
SYSTEM_PROMPT = (
    "Eres un analista inmobiliario. Tu ÚNICA función es emitir juicio cualitativo "
    "estructurado sobre un inmueble a partir de su anuncio.\n\n"
    "NO calcules rentabilidades, ROI, porcentajes, scores ni ningún importe derivado "
    "de una operación aritmética. Otro sistema hace esos cálculos. Tu única función es "
    "emitir juicio cualitativo estructurado. Si no puedes inferir un campo del texto "
    "disponible, usa DESCONOCIDO o inclúyelo en `campos_no_inferibles`. Jamás inventes "
    "ni estimes un valor plausible.\n\n"
    "Devuelve EXCLUSIVAMENTE el JSON que cumple el esquema indicado. Para "
    "`senales_riesgo` y `senales_oportunidad` usa SOLO los códigos del catálogo que se "
    "te proporciona para el país del inmueble; si ninguno aplica, usa lista vacía.\n\n"
    "`menciona_exencion_fiscal`: responde SI solo si el anuncio menciona "
    "explícitamente CONFOTUR, la Ley 158-01 o una exención de impuestos; NO si "
    "afirma explícitamente que no la tiene; DUDOSO en cualquier otro caso, "
    "incluido el habitual de que el anuncio no diga nada al respecto. Es una "
    "SEÑAL de lectura del texto, no un juicio sobre si el inmueble está acogido: "
    "eso lo confirma el propietario. Ante la duda, DUDOSO."
)

VERSION_MAX_REINTENTOS = 2


@dataclass
class ResultadoAnalisis:
    analisis: AnalisisCualitativo | None
    hash_contenido: str
    tokens_entrada: int
    tokens_salida: int
    modelo: str
    fallido: bool
    # Tokens de CACHÉ. Sin esto el coste real era invisible: la escritura de
    # caché cuesta 1.25x la entrada y la lectura 0.1x, así que contar solo
    # entrada/salida puede errar el gasto por completo.
    tokens_cache_write: int = 0
    tokens_cache_read: int = 0
    # Última excepción cuando `fallido`. Antes se perdía: el bucle atrapaba
    # cualquier error y seguía, así que un job salía con coste 0.0000 y sin
    # pista de si era la clave de la API, el modelo o la red.
    error: str | None = None


def _hash_contenido(inmueble: Inmueble) -> str:
    base = json.dumps(
        {"titulo": inmueble.titulo, "descripcion": inmueble.descripcion_completa,
         "caracteristicas": inmueble.caracteristicas_listadas,
         "precio": str(inmueble.precio), "ciudad": inmueble.ciudad},
        sort_keys=True, ensure_ascii=False,
    )
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _prompt_usuario(inmueble: Inmueble, codigos_riesgo: list[str], codigos_oport: list[str]) -> str:
    return (
        f"ANUNCIO A ANALIZAR (país {inmueble.pais or 'DESCONOCIDO'}):\n"
        f"Título: {inmueble.titulo}\n"
        f"Precio: {inmueble.precio} {inmueble.moneda or ''}\n"
        f"Superficie construida: {inmueble.superficie_construida_m2} m²\n"
        f"Superficie útil: {inmueble.superficie_util_m2} m²\n"
        f"Ciudad/Barrio: {inmueble.ciudad} / {inmueble.barrio}\n"
        f"Características: {', '.join(inmueble.caracteristicas_listadas)}\n"
        f"Descripción:\n{inmueble.descripcion_completa}\n\n"
        f"Códigos de RIESGO válidos para este país: {codigos_riesgo or ['(ninguno configurado)']}\n"
        f"Códigos de OPORTUNIDAD válidos para este país: {codigos_oport or ['(ninguno)']}\n"
    )


def _esquema() -> dict:
    esquema = AnalisisCualitativo.model_json_schema()
    esquema["additionalProperties"] = False
    # `senales_no_reconocidas` la calcula el sistema al cruzar la salida de Claude
    # contra el catálogo del país; Claude NUNCA la emite → fuera de su esquema.
    esquema.get("properties", {}).pop("senales_no_reconocidas", None)
    if "senales_no_reconocidas" in esquema.get("required", []):
        esquema["required"].remove("senales_no_reconocidas")
    return esquema


# --- Salida estructurada por TOOL USE, no por `output_config` -----------------
# El primer análisis real reventó con `output_config` (feature de structured outputs
# que existe en anthropic 0.116.0 pero NO en la 0.42.0 que instala el contenedor).
# `tool use` —forzar una tool cuyo `input_schema` es el esquema del análisis— está
# presente en AMBAS versiones (verificado por introspección) y es el mecanismo
# estable. El modelo devuelve un bloque `tool_use` cuyo `input` es el JSON; la
# conformidad la garantiza Pydantic (extra='forbid') + reintentos, no la API.
_NOMBRE_TOOL = "registrar_analisis_cualitativo"


def _tool() -> dict:
    """La tool que fuerza la salida estructurada. Su `input_schema` ES `_esquema()`,
    así que la barrera anti-números (test) sigue cubriendo lo que se le pide a Claude."""
    return {
        "name": _NOMBRE_TOOL,
        "description": (
            "Registra el juicio cualitativo del inmueble. SOLO categorías, enums, "
            "booleanos y texto corto; NUNCA cifras calculadas (ROI, rentabilidades, "
            "porcentajes): de eso se encarga otro sistema."
        ),
        "input_schema": _esquema(),
    }


def verificar_sdk() -> None:
    """Comprueba, AL ARRANCAR, que el SDK de Anthropic acepta lo que este código usa.

    Requisito explícito: preferir un contenedor que no arranca a nueve análisis
    fallidos en silencio. El primer análisis real falló porque la firma de
    `messages.create` cambió entre versiones (`output_config` en 0.116.0, ausente
    en la 0.42.0 desplegada). Esto lo caza en el arranque, no en mitad de un lote.

    Solo inspecciona la firma (sin red ni clave real): valida capacidad del SDK,
    no autenticación —eso lo cubre `scripts/probar_analista.py` con una llamada real.
    """
    import inspect

    try:
        import anthropic
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "El paquete `anthropic` no está instalado. Ejecuta "
            "`pip install -r requirements.txt`."
        ) from e

    try:
        cliente = anthropic.AsyncAnthropic(api_key="verificacion-de-arranque")
        parametros = set(inspect.signature(cliente.messages.create).parameters)
    except Exception as e:  # noqa: BLE001  # pragma: no cover
        raise RuntimeError(
            f"No se pudo inspeccionar el SDK de Anthropic para verificarlo: {e}"
        ) from e

    requeridos = {"tools", "tool_choice", "system", "messages", "model", "max_tokens"}
    faltan = requeridos - parametros
    if faltan:
        version = getattr(anthropic, "__version__", "desconocida")
        raise RuntimeError(
            f"El SDK de Anthropic instalado (anthropic {version}) no acepta "
            f"{sorted(faltan)}. El analista usa 'tool use' (tools + tool_choice), "
            "presente desde 0.42.0. Alinea `requirements.txt` con una versión que lo "
            "soporte y reconstruye la imagen. Se aborta el arranque a propósito: es "
            "preferible a que fallen los análisis uno a uno más tarde."
        )


# Sentinela de "sin señal": ni surte efecto ni se marca como no reconocida.
_SENALES_BENIGNAS = {"NINGUNA"}


def _unicos(codigos: list[str]) -> list[str]:
    """Deduplica preservando el orden de aparición."""
    vistos: set[str] = set()
    salida: list[str] = []
    for codigo in codigos:
        if codigo not in vistos:
            vistos.add(codigo)
            salida.append(codigo)
    return salida


def validar_senales(
    analisis: AnalisisCualitativo,
    codigos_riesgo: list[str],
    codigos_oportunidad: list[str],
) -> AnalisisCualitativo:
    """Cruza las señales de Claude contra el catálogo del país del inmueble.

    - Un código dentro de catálogo se conserva en su lista (surtirá efecto en el
      scoring: descarte duro o penalización ponderable).
    - Un código fuera de catálogo NO se descarta en silencio: se separa a
      `senales_no_reconocidas`, visible en la ficha y el monitor. Un código ahí
      significa o bien que Claude alucina, o bien que falta un código en el catálogo
      de ese país; en ambos casos el propietario debe verlo, no ignorarlo.

    Función pura (sin I/O): recibe los catálogos ya resueltos y devuelve un modelo
    nuevo con las señales repartidas. `senales_riesgo` se valida contra los riesgos
    del país; `senales_oportunidad` contra las oportunidades del catálogo.
    """
    validos_riesgo = set(codigos_riesgo)
    validos_oport = set(codigos_oportunidad)
    riesgo_ok: list[str] = []
    oport_ok: list[str] = []
    no_reconocidas: list[str] = []

    for codigo in analisis.senales_riesgo:
        if codigo in _SENALES_BENIGNAS:
            continue
        (riesgo_ok if codigo in validos_riesgo else no_reconocidas).append(codigo)
    for codigo in analisis.senales_oportunidad:
        if codigo in _SENALES_BENIGNAS:
            continue
        (oport_ok if codigo in validos_oport else no_reconocidas).append(codigo)

    return analisis.model_copy(
        update={
            "senales_riesgo": _unicos(riesgo_ok),
            "senales_oportunidad": _unicos(oport_ok),
            "senales_no_reconocidas": _unicos(no_reconocidas),
        }
    )


async def analizar(
    inmueble: Inmueble,
    codigos_riesgo: list[str],
    codigos_oportunidad: list[str],
) -> ResultadoAnalisis:
    """Llama a Claude y devuelve el análisis validado (o fallido)."""
    import anthropic

    cfg = obtener_config()
    cliente = anthropic.AsyncAnthropic(api_key=cfg.anthropic_api_key)
    hash_c = _hash_contenido(inmueble)
    usuario = _prompt_usuario(inmueble, codigos_riesgo, codigos_oportunidad)

    tokens_in = tokens_out = 0
    cache_w = cache_r = 0
    ultimo_error: str | None = None
    for _ in range(VERSION_MAX_REINTENTOS + 1):
        try:
            resp = await cliente.messages.create(
                model=cfg.anthropic_model,
                max_tokens=cfg.anthropic_max_tokens,
                # Caché de prompt sobre el prefijo CONSTANTE. El orden de caché es
                # tools → system → messages, así que un breakpoint en `system`
                # cachea tools+system: el esquema de la tool (~1.500 tokens) más
                # este prompt, idénticos en cada llamada. Solo varía el anuncio,
                # que va en `messages` y queda fuera del prefijo.
                #
                # Supera el mínimo de Sonnet 5 (1.024 tokens); si algún día no lo
                # superara, la API simplemente no cachea y `cache_*` vienen a 0 —
                # el dashboard lo enseñaría, no fallaría en silencio.
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                messages=[{"role": "user", "content": usuario}],
                tools=[_tool()],
                # Forzar la tool: el modelo DEBE devolver un bloque tool_use con el
                # análisis, no prosa. La conformidad con el esquema la garantiza
                # Pydantic abajo, no la API (así vale igual en 0.42.0 sin `strict`).
                tool_choice={"type": "tool", "name": _NOMBRE_TOOL},
            )
            tokens_in += resp.usage.input_tokens
            tokens_out += resp.usage.output_tokens
            # Presentes en 0.42.0 y 0.116.0 (verificado). Pueden venir a None.
            cache_w += getattr(resp.usage, "cache_creation_input_tokens", 0) or 0
            cache_r += getattr(resp.usage, "cache_read_input_tokens", 0) or 0
            bloque = next(
                (b for b in resp.content
                 if getattr(b, "type", None) == "tool_use"
                 and getattr(b, "name", None) == _NOMBRE_TOOL),
                None,
            )
            if bloque is None:
                # Con tool_choice forzado no debería ocurrir; si ocurre (p. ej.
                # refusal de seguridad), se dice en claro en vez de tragarlo.
                raise ValueError(
                    f"La respuesta no trae el bloque tool_use '{_NOMBRE_TOOL}' "
                    f"(stop_reason={getattr(resp, 'stop_reason', '?')})"
                )
            # `bloque.input` YA es un dict (tool use lo entrega parseado, no como
            # texto). Se valida con Pydantic: extra='forbid' rechaza cualquier campo
            # no declarado y el esquema no tiene campos numéricos (Principio 1).
            analisis = AnalisisCualitativo.model_validate(bloque.input)
            # Endurecimiento: cruza las señales contra el catálogo del país; los
            # códigos fuera de catálogo van a `senales_no_reconocidas` (no se pierden).
            analisis = validar_senales(analisis, codigos_riesgo, codigos_oportunidad)
            return ResultadoAnalisis(
                analisis=analisis, hash_contenido=hash_c,
                tokens_entrada=tokens_in, tokens_salida=tokens_out,
                tokens_cache_write=cache_w, tokens_cache_read=cache_r,
                modelo=cfg.anthropic_model, fallido=False,
            )
        except Exception as e:
            # Se sigue reintentando (un JSON mal formado suele arreglarse solo),
            # pero el motivo ya no se tira: sin él, un lote entero puede fallar
            # sin que nadie sepa por qué.
            ultimo_error = f"{type(e).__name__}: {e}"[:800]
            continue

    return ResultadoAnalisis(
        analisis=None, hash_contenido=hash_c,
        tokens_entrada=tokens_in, tokens_salida=tokens_out,
        tokens_cache_write=cache_w, tokens_cache_read=cache_r,
        modelo=cfg.anthropic_model, fallido=True, error=ultimo_error,
    )
