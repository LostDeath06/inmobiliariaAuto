"""Contrato de la salida estructurada del analista (tool use).

El primer análisis real falló porque el código usaba `output_config`, que existe en
anthropic 0.116.0 pero NO en la 0.42.0 que instala el contenedor. El arreglo pasó a
`tool use` (tools + tool_choice), presente en ambas versiones. Estos tests fijan ese
contrato para que nadie lo revierta sin que un test rojo lo avise.
"""

from backend.servicios.analista_cualitativo import (
    _NOMBRE_TOOL,
    _esquema,
    _tool,
    verificar_sdk,
)

# Tipos que, si aparecen en el esquema forzado, cruzarían el Principio 1
# (Claude no emite números calculados). Espejo del test anti-números, aplicado
# aquí sobre el `input_schema` de la tool, que es lo que de verdad se le manda.
_TIPOS_NUMERICOS = {"integer", "number"}


def test_la_tool_envuelve_el_esquema_del_analisis():
    """El `input_schema` de la tool ES el esquema del análisis, sin desviarse.

    Si divergieran, la barrera anti-números (que inspecciona `_esquema()`) dejaría
    de cubrir lo que realmente se le pide al modelo.
    """
    tool = _tool()
    assert tool["name"] == _NOMBRE_TOOL
    assert tool["input_schema"] == _esquema()
    assert tool["input_schema"]["additionalProperties"] is False


def test_el_esquema_forzado_no_tiene_campos_numericos():
    """Barrera del Principio 1 sobre el input_schema de la tool.

    Recorre las propiedades (y las de `$defs`) y falla si alguna declara un tipo
    numérico: Claude solo emite categorías, enums, booleanos y texto.
    """
    esquema = _tool()["input_schema"]

    def tipos_de(nodo: dict) -> set[str]:
        t = nodo.get("type")
        if isinstance(t, str):
            return {t}
        if isinstance(t, list):
            return set(t)
        return set()

    numericos = []
    for nombre, prop in esquema.get("properties", {}).items():
        if tipos_de(prop) & _TIPOS_NUMERICOS:
            numericos.append(nombre)
    for defn, cuerpo in esquema.get("$defs", {}).items():
        for nombre, prop in cuerpo.get("properties", {}).items():
            if tipos_de(prop) & _TIPOS_NUMERICOS:
                numericos.append(f"{defn}.{nombre}")

    assert not numericos, f"El esquema forzado a Claude tiene campos numéricos: {numericos}"


def test_no_reconocidas_no_se_le_pide_a_claude():
    """`senales_no_reconocidas` la calcula el sistema; nunca la emite Claude."""
    esquema = _tool()["input_schema"]
    assert "senales_no_reconocidas" not in esquema.get("properties", {})
    assert "senales_no_reconocidas" not in esquema.get("required", [])


def test_verificar_sdk_pasa_con_el_sdk_instalado():
    """El SDK instalado (en CI y en el contenedor) soporta tool use.

    Si alguien reintrodujera `output_config` no lo cazaría este test, pero si el
    SDK se degradara a uno sin tool use, `verificar_sdk` lanzaría y esto fallaría
    en CI antes de llegar al VPS.
    """
    verificar_sdk()  # no debe lanzar


def test_verificar_sdk_falla_ruidosamente_si_falta_tool_use(monkeypatch):
    """Requisito 5: un SDK sin tool use debe abortar el arranque, no fallar en el
    primer análisis. Se simula un SDK cuyo `messages.create` no acepta tool_choice."""
    import sys
    import types

    def create(self, *, model, max_tokens, messages, system=None, **kwargs):
        # Firma SIN tools/tool_choice: como una versión demasiado vieja.
        ...

    cliente = types.SimpleNamespace(messages=types.SimpleNamespace(create=create))
    falso = types.ModuleType("anthropic")
    falso.__version__ = "0.0.1-falso"
    falso.AsyncAnthropic = lambda **kw: cliente
    monkeypatch.setitem(sys.modules, "anthropic", falso)

    import pytest

    with pytest.raises(RuntimeError, match="tool_choice"):
        verificar_sdk()
