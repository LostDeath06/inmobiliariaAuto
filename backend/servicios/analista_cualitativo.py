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
    ultimo_error: str | None = None
    for _ in range(VERSION_MAX_REINTENTOS + 1):
        try:
            resp = await cliente.messages.create(
                model=cfg.anthropic_model,
                max_tokens=cfg.anthropic_max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": usuario}],
                output_config={"format": {"type": "json_schema", "schema": _esquema()}},
            )
            tokens_in += resp.usage.input_tokens
            tokens_out += resp.usage.output_tokens
            texto = next((b.text for b in resp.content if b.type == "text"), "")
            analisis = AnalisisCualitativo.model_validate_json(texto)
            # Endurecimiento: cruza las señales contra el catálogo del país; los
            # códigos fuera de catálogo van a `senales_no_reconocidas` (no se pierden).
            analisis = validar_senales(analisis, codigos_riesgo, codigos_oportunidad)
            return ResultadoAnalisis(
                analisis=analisis, hash_contenido=hash_c,
                tokens_entrada=tokens_in, tokens_salida=tokens_out,
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
        modelo=cfg.anthropic_model, fallido=True, error=ultimo_error,
    )
