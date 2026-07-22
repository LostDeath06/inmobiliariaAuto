"""Script de humo del analista cualitativo (Fase 6).

Prueba la llamada REAL a Claude sobre UN solo anuncio de ejemplo, para reducir el
riesgo antes de enchufar la API key a un lote entero. Si el manejo de enums/`$defs`
en structured outputs falla, lo ves aquí en 10 segundos.

Uso:
    # Windows PowerShell
    $env:ANTHROPIC_API_KEY="sk-ant-..."; python scripts/probar_analista.py
    # bash
    ANTHROPIC_API_KEY="sk-ant-..." python scripts/probar_analista.py

Qué hace:
1. Imprime el ESQUEMA exacto que se le fuerza a Claude (el mismo que usa el pipeline).
2. Llama a la API con el system prompt y el esquema reales.
3. Imprime la RESPUESTA CRUDA de Claude.
4. Intenta parsearla con Pydantic (AnalisisCualitativo).
5. Falla RUIDOSAMENTE y con mensaje claro si algo no valida (salida != 0).

Los datos del anuncio son FICTICIOS y están marcados como tales — nunca se mezclan
con configuración real.
"""

from __future__ import annotations

import json
import os
import sys
from uuid import uuid4

# Permite ejecutar el script desde la raíz del repo.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.modelos.analisis import AnalisisCualitativo  # noqa: E402
from backend.modelos.pipeline import Inmueble  # noqa: E402
from backend.nucleo.config import obtener_config  # noqa: E402
from backend.servicios.analista_cualitativo import (  # noqa: E402
    SYSTEM_PROMPT,
    _esquema,
    _prompt_usuario,
    validar_senales,
)

# La consola de Windows es cp1252: un carácter no-ASCII en un print reventaría el
# script con UnicodeEncodeError y taparía el error real que venías a diagnosticar.
# Esta es una red de seguridad: tiene que fallar por lo que falla, no por el encoding.
for _flujo in (sys.stdout, sys.stderr):
    try:
        _flujo.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        pass


def _error(msg: str, codigo: int = 1) -> None:
    print(f"\n[FALLO] {msg}", file=sys.stderr)
    sys.exit(codigo)


# --- Anuncio de EJEMPLO (ficticio, marcado como tal) -------------------------
INMUEBLE_DEMO = Inmueble(
    id=uuid4(),
    portal_id=uuid4(),
    url_anuncio="https://ejemplo-ficticio/anuncio-demo",
    hash_deduplicacion="demo",
    titulo="[DEMO] Piso a reformar en el centro, con mucha luz",
    precio=None,  # el precio no se le da a Claude para juzgar; solo texto cualitativo
    moneda="EUR",
    superficie_util_m2=None,
    ciudad="Valencia",
    barrio="Ruzafa",
    pais="ES",
    descripcion_completa=(
        "[DATOS FICTICIOS DE PRUEBA] Piso de particular, procedente de herencia, "
        "necesita reforma integral: instalación eléctrica y fontanería antiguas, "
        "cocina y baño originales. Cuarto piso sin ascensor. Muy luminoso, exterior. "
        "Se vende con prisa. No tiene cédula de habitabilidad. Ideal inversores."
    ),
    caracteristicas_listadas=["Exterior", "Para reformar", "Particular", "Sin ascensor"],
)

# Códigos de catálogo de ejemplo (los que aplicarían en ES).
CODIGOS_RIESGO = ["OKUPAS", "DERRIBO", "CARGAS", "SIN_CEDULA", "SUBASTA", "PROINDIVISO"]
CODIGOS_OPORTUNIDAD = ["VENTA_URGENTE", "HERENCIA", "PARTICULAR_SIN_AGENCIA",
                       "REFORMABLE_CON_MARGEN", "PRECIO_REBAJADO"]


def main() -> None:
    cfg = obtener_config()

    if not cfg.anthropic_api_key:
        _error(
            "No hay ANTHROPIC_API_KEY en el entorno. Expórtala antes de ejecutar:\n"
            '   PowerShell:  $env:ANTHROPIC_API_KEY="sk-ant-..."\n'
            '   bash:        export ANTHROPIC_API_KEY="sk-ant-..."'
        )

    try:
        import anthropic
    except ImportError:
        _error("Falta el paquete `anthropic`. Instala: pip install -r requirements.txt")

    esquema = _esquema()
    usuario = _prompt_usuario(INMUEBLE_DEMO, CODIGOS_RIESGO, CODIGOS_OPORTUNIDAD)

    print("=" * 70)
    print(f"MODELO: {cfg.anthropic_model}")
    print("=" * 70)
    print("\n--- ESQUEMA forzado a Claude (structured outputs) ---")
    print(json.dumps(esquema, indent=2, ensure_ascii=False))

    print("\n--- Llamando a la API… ---")
    cliente = anthropic.Anthropic(api_key=cfg.anthropic_api_key)
    try:
        resp = cliente.messages.create(
            model=cfg.anthropic_model,
            max_tokens=cfg.anthropic_max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": usuario}],
            output_config={"format": {"type": "json_schema", "schema": esquema}},
        )
    except Exception as e:  # noqa: BLE001
        _error(
            f"La API rechazó la petición ({type(e).__name__}): {e}\n"
            "Causa típica: el esquema de structured outputs no le gusta a la API "
            "(enums/$defs/additionalProperties). Este es exactamente el fallo que "
            "queríamos cazar aquí y no en mitad de un lote."
        )

    texto = next((b.text for b in resp.content if getattr(b, "type", None) == "text"), "")

    print("\n--- RESPUESTA CRUDA de Claude ---")
    print(texto)
    print(f"\n(tokens entrada={resp.usage.input_tokens}, salida={resp.usage.output_tokens})")
    if resp.stop_reason == "refusal":
        _error("Claude rechazó la petición (stop_reason=refusal). Revisa el contenido.")

    print("\n--- Parseo Pydantic (AnalisisCualitativo) ---")
    try:
        analisis = AnalisisCualitativo.model_validate_json(texto)
    except Exception as e:  # noqa: BLE001
        _error(
            f"El JSON de Claude NO valida contra AnalisisCualitativo:\n{e}\n"
            "Revisa: campos extra (extra='forbid'), enums fuera de rango, o números "
            "donde debía haber categorías."
        )

    print("[OK] Valida. Analisis crudo parseado:")
    print(json.dumps(analisis.model_dump(), indent=2, ensure_ascii=False))

    # Segundo frente: que valide no basta. Un código fuera de catálogo pasa Pydantic
    # (senales_* son list[str]) y luego no cruza con nada. Aquí se ve en la primera
    # llamada real, que es justo para lo que existe este script.
    print("\n--- Cruce de senales contra el catalogo del pais (validar_senales) ---")
    validado = validar_senales(analisis, CODIGOS_RIESGO, CODIGOS_OPORTUNIDAD)
    print(f"  riesgo aplicables    : {validado.senales_riesgo}")
    print(f"  oportunidad aplicables: {validado.senales_oportunidad}")
    if validado.senales_no_reconocidas:
        print(f"  FUERA DE CATALOGO    : {validado.senales_no_reconocidas}")
        print(
            "\n[AVISO] Claude devolvio codigos que el catalogo de ejemplo no contempla.\n"
            "  No es un fallo del script: es la senal que buscabamos. Significa una de dos:\n"
            "    a) el modelo esta inventando codigos -> aprieta el prompt, o\n"
            "    b) falta ese codigo en el catalogo de ese pais -> anadelo en `riesgos_pais`.\n"
            "  Mientras tanto esas senales NO se aplican al score y el inmueble se marca\n"
            "  PARCIAL (nunca COMPLETO) para que no te fies de mas."
        )
    else:
        print("  Sin codigos fuera de catalogo: el modelo se cino al catalogo.")

    print("\n[HUMO OK] La llamada real a Claude funciona y el JSON valida.")


if __name__ == "__main__":
    main()
