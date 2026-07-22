"""Test anti-números del analista (protege el Principio 1).

Verifica que el esquema de salida de Claude no contiene NINGÚN campo numérico
(integer/number): Claude solo emite juicio cualitativo. Y que el system prompt
lleva textualmente la prohibición de §8.3.
"""

import json

from backend.modelos.analisis import AnalisisCualitativo
from backend.servicios.analista_cualitativo import SYSTEM_PROMPT


def _tipos_en_esquema(esquema: dict) -> set[str]:
    tipos = set()

    def recorrer(nodo):
        if isinstance(nodo, dict):
            t = nodo.get("type")
            if isinstance(t, str):
                tipos.add(t)
            elif isinstance(t, list):
                tipos.update(t)
            for v in nodo.values():
                recorrer(v)
        elif isinstance(nodo, list):
            for v in nodo:
                recorrer(v)

    recorrer(esquema)
    return tipos


def test_esquema_del_analista_no_tiene_campos_numericos():
    esquema = AnalisisCualitativo.model_json_schema()
    tipos = _tipos_en_esquema(esquema)
    assert "integer" not in tipos, f"El análisis NO puede tener enteros. Tipos: {tipos}"
    assert "number" not in tipos, f"El análisis NO puede tener números. Tipos: {tipos}"


def test_ningun_campo_del_modelo_es_int_o_float():
    for nombre, campo in AnalisisCualitativo.model_fields.items():
        anotacion = repr(campo.annotation)
        assert "int" not in anotacion.split("'"), f"{nombre} parece entero"
        assert "float" not in anotacion.split("'"), f"{nombre} parece float"


def test_system_prompt_contiene_la_prohibicion():
    assert "NO calcules rentabilidades, ROI, porcentajes, scores" in SYSTEM_PROMPT
    assert "Jamás inventes ni estimes un valor plausible" in SYSTEM_PROMPT


def test_el_detector_caza_un_numero_real():
    # Control: un esquema con un entero DEBE ser detectado.
    esquema_malo = {"properties": {"roi": {"type": "number"}}}
    assert "number" in _tipos_en_esquema(esquema_malo)
