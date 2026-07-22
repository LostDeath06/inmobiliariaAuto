"""Generador de prompt dinámico para OpenClaw.

El prompt es libre (esto hace el sistema agnóstico a portales); la salida NO.
Plantilla parametrizada: recibe una Búsqueda + Portal y genera el texto en lenguaje
natural + el JSON Schema de salida obligatorio (§5.4) + la regla `null` antes que
invención, escrita de forma enfática.
"""

from __future__ import annotations

import json

from ..modelos.configuracion import Portal
from ..modelos.pipeline import Busqueda

# JSON Schema de salida (§5.4, multi-divisa: precio + moneda).
ESQUEMA_SALIDA: dict = {
    "job_id": "string (uuid, obligatorio)",
    "portal_url": "string (obligatorio)",
    "portal_nombre": "string | null",
    "fecha_extraccion_utc": "string ISO-8601 (obligatorio)",
    "busqueda_ejecutada": {
        "ciudad": "string | null",
        "presupuesto_min": "number | null",
        "presupuesto_max": "number | null",
        "moneda": "string ISO-4217 | null",
        "tipo_inmueble": "string | null",
        "filtros_aplicados": ["string"],
        "url_resultados": "string | null",
    },
    "total_resultados_detectados": "integer | null",
    "total_anuncios_extraidos": "integer (obligatorio)",
    "anuncios": [
        {
            "url_anuncio": "string (obligatorio, único)",
            "id_portal": "string | null",
            "titulo": "string | null",
            "precio": "number | null",
            "moneda": "string ISO-4217 | null (EUR, USD, DOP, ...)",
            "superficie_construida_m2": "number | null",
            "superficie_util_m2": "number | null",
            "habitaciones": "integer | null",
            "banos": "integer | null",
            "planta": "string | null",
            "tiene_ascensor": "boolean | null",
            "ano_construccion": "integer | null",
            "certificado_energetico": "string | null",
            "direccion_texto": "string | null",
            "barrio": "string | null",
            "ciudad": "string | null",
            "provincia": "string | null",
            "pais": "string | null",
            "codigo_postal": "string | null",
            "latitud": "number | null",
            "longitud": "number | null",
            "descripcion_completa": "string | null",
            "caracteristicas_listadas": ["string"],
            "urls_imagenes": ["string"],
            "tipo_anunciante": "PARTICULAR | AGENCIA | PROMOTOR | DESCONOCIDO | null",
            "fecha_publicacion": "string ISO-8601 | null",
            "gastos_comunidad_mes": "number | null",
            "campos_no_encontrados": ["string"],
            "notas_extraccion": "string | null",
        }
    ],
    "errores_navegacion": ["string"],
    "advertencias": ["string"],
    "extraccion_completa": "boolean (obligatorio)",
}

_REGLA_NULL = """
REGLA INNEGOCIABLE — `null` ANTES QUE INVENCIÓN:
- Si un campo no aparece en el anuncio, devuélvelo como `null` explícito.
- Si no pudiste leer un campo, devuélvelo como `null` explícito y añádelo a
  `campos_no_encontrados`.
- JAMÁS inventes, estimes ni pongas un valor "plausible". Un dato inventado es peor
  que un dato ausente: contamina todo el análisis en silencio.
- El `precio` va SIEMPRE con su `moneda` (ISO-4217). Si no puedes determinar la
  moneda, deja precio y moneda en `null`.
"""


def construir(busqueda: Busqueda, portal: Portal, limite_anuncios: int, job_id: str) -> str:
    """Genera el prompt en lenguaje natural para OpenClaw."""
    partes: list[str] = []
    partes.append(
        "Eres un agente de extracción inmobiliaria. Tu tarea es navegar el portal "
        "indicado, aplicar los filtros de búsqueda y extraer los anuncios en el "
        "formato JSON exacto especificado más abajo."
    )
    partes.append(f"\nJOB ID (debes devolverlo tal cual): {job_id}")
    partes.append(f"\n1) PORTAL RAÍZ: {portal.url_raiz}  (nombre: {portal.nombre})")

    criterios = []
    if busqueda.ciudad:
        criterios.append(f"ciudad = {busqueda.ciudad}")
    if busqueda.presupuesto_min is not None:
        criterios.append(f"presupuesto mínimo = {busqueda.presupuesto_min} {busqueda.moneda or ''}")
    if busqueda.presupuesto_max is not None:
        criterios.append(f"presupuesto máximo = {busqueda.presupuesto_max} {busqueda.moneda or ''}")
    if busqueda.tipo_inmueble:
        criterios.append(f"tipo de inmueble = {busqueda.tipo_inmueble}")
    for clave, valor in (busqueda.filtros_extra or {}).items():
        criterios.append(f"{clave} = {valor}")
    partes.append("\n2) PARÁMETROS DE BÚSQUEDA:\n   - " + "\n   - ".join(criterios or ["(sin filtros)"]))

    partes.append(
        "\n3) Aplica estos filtros usando los controles nativos del portal "
        "(desplegables, sliders, casillas). No filtres a mano después."
    )
    partes.append(
        "\n4) Abre CADA anuncio individual y extrae en profundidad todos los campos "
        "del esquema (no te quedes en la lista de resultados)."
    )
    partes.append(
        f"\n5) LÍMITE: extrae como máximo {limite_anuncios} anuncios (controla coste y "
        "tiempo). Si hay más resultados, marca `extraccion_completa: false`."
    )
    partes.append("\n6) FORMATO DE SALIDA OBLIGATORIO (devuelve exactamente esta forma):")
    partes.append("```json\n" + json.dumps(ESQUEMA_SALIDA, indent=2, ensure_ascii=False) + "\n```")
    partes.append(_REGLA_NULL)
    partes.append(
        "\n7) ERRORES: si una página falla, un anuncio no carga o hay un captcha, "
        "REPÓRTALO en `errores_navegacion` o `advertencias` y sigue con los demás. "
        "Nunca abortes el job entero por un fallo individual. Nunca inventes para "
        "'rellenar'."
    )
    return "\n".join(partes)
