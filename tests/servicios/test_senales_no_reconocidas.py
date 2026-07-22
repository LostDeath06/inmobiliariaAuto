"""Endurecimiento del cruce de señales contra el catálogo del país.

El catálogo de riesgos vive en BD y varía por país. Un código que Claude devuelva
fuera de catálogo (inventado o mal escrito) no cruzaría con nada en el scoring: ni
dispararía descarte duro ni penalización, se ignoraría en silencio. Eso es un fallo
silencioso: un riesgo real podría quedar sin efecto sin que el propietario lo vea.

`validar_senales` lo evita: los códigos fuera de catálogo NO se pierden, se separan
a `senales_no_reconocidas` (campo visible). Estos tests fijan ese contrato.
"""

from backend.modelos.analisis import AnalisisCualitativo
from backend.modelos.enumeraciones import (
    AptoTernario,
    CalidadDescripcion,
    CoherenciaPrecio,
    EstadoConservacion,
    NivelConfianza,
    NivelReforma,
    Tipologia,
)
from backend.servicios.analista_cualitativo import _esquema, validar_senales

# Catálogo de ejemplo (como el que el pipeline resuelve desde BD por país).
RIESGOS_ES = ["CARGAS", "PROINDIVISO", "OKUPAS", "SUBASTA"]
OPORTUNIDADES = ["INFRAVALORADO", "REVALORIZACION_ZONA"]


def _analisis(**overrides) -> AnalisisCualitativo:
    base = dict(
        estado_conservacion=EstadoConservacion.BUEN_ESTADO,
        nivel_reforma_estimado=NivelReforma.NINGUNA,
        tipologia=Tipologia.PISO,
        senales_riesgo=[],
        senales_oportunidad=[],
        apto_alquiler_larga_estancia=AptoTernario.SI,
        apto_alquiler_turistico=AptoTernario.NO,
        potencial_division_horizontal=AptoTernario.NO,
        calidad_descripcion=CalidadDescripcion.ESTANDAR,
        coherencia_precio_descripcion=CoherenciaPrecio.COHERENTE,
        resumen_analista="Piso correcto.",
        nivel_confianza=NivelConfianza.MEDIA,
    )
    base.update(overrides)
    return AnalisisCualitativo(**base)


def test_codigo_de_riesgo_fuera_de_catalogo_va_a_no_reconocidas():
    """Un código inventado NO se pierde: acaba en `senales_no_reconocidas`."""
    analisis = _analisis(senales_riesgo=["CARGAS", "OKUPAS_FANTASMA"])
    validado = validar_senales(analisis, RIESGOS_ES, OPORTUNIDADES)

    # El inventado se separa a no_reconocidas, y NO queda en senales_riesgo.
    assert "OKUPAS_FANTASMA" in validado.senales_no_reconocidas
    assert "OKUPAS_FANTASMA" not in validado.senales_riesgo
    # El del catálogo se conserva para que surta efecto en el scoring.
    assert validado.senales_riesgo == ["CARGAS"]


def test_codigo_de_oportunidad_fuera_de_catalogo_va_a_no_reconocidas():
    analisis = _analisis(senales_oportunidad=["INFRAVALORADO", "CHOLLO_MAGICO"])
    validado = validar_senales(analisis, RIESGOS_ES, OPORTUNIDADES)

    assert "CHOLLO_MAGICO" in validado.senales_no_reconocidas
    assert "CHOLLO_MAGICO" not in validado.senales_oportunidad
    assert validado.senales_oportunidad == ["INFRAVALORADO"]


def test_todos_los_codigos_en_catalogo_no_producen_no_reconocidas():
    analisis = _analisis(
        senales_riesgo=["CARGAS", "SUBASTA"],
        senales_oportunidad=["INFRAVALORADO"],
    )
    validado = validar_senales(analisis, RIESGOS_ES, OPORTUNIDADES)

    assert validado.senales_no_reconocidas == []
    assert validado.senales_riesgo == ["CARGAS", "SUBASTA"]
    assert validado.senales_oportunidad == ["INFRAVALORADO"]


def test_pais_sin_catalogo_marca_todo_como_no_reconocido():
    """DO/VE aún sin `riesgos_pais`: cada código emitido es un aviso, no un silencio."""
    analisis = _analisis(senales_riesgo=["OCUPACION_INFORMAL", "LITIGIO_JUDICIAL"])
    validado = validar_senales(analisis, [], [])

    assert validado.senales_riesgo == []
    assert set(validado.senales_no_reconocidas) == {"OCUPACION_INFORMAL", "LITIGIO_JUDICIAL"}


def test_sentinela_ninguna_no_se_marca_como_no_reconocida():
    """`NINGUNA` significa 'sin señal': ni se aplica ni ensucia no_reconocidas."""
    analisis = _analisis(senales_oportunidad=["NINGUNA"])
    validado = validar_senales(analisis, RIESGOS_ES, OPORTUNIDADES)

    assert validado.senales_no_reconocidas == []
    assert validado.senales_oportunidad == []


def test_codigos_repetidos_se_deduplican():
    analisis = _analisis(senales_riesgo=["XXX", "XXX", "CARGAS"])
    validado = validar_senales(analisis, RIESGOS_ES, OPORTUNIDADES)

    assert validado.senales_no_reconocidas == ["XXX"]
    assert validado.senales_riesgo == ["CARGAS"]


def test_no_reconocidas_sobrevive_la_serializacion():
    """'Nunca se pierde': el campo cruza ida y vuelta por JSON sin desaparecer."""
    analisis = _analisis(senales_riesgo=["INVENTADO"])
    validado = validar_senales(analisis, RIESGOS_ES, OPORTUNIDADES)

    recuperado = AnalisisCualitativo.model_validate_json(validado.model_dump_json())
    assert recuperado.senales_no_reconocidas == ["INVENTADO"]


def test_claude_no_emite_no_reconocidas_pero_el_modelo_la_lleva():
    """El campo lo calcula el sistema: fuera del esquema de Claude, dentro del modelo."""
    propiedades = _esquema().get("properties", {})
    assert "senales_no_reconocidas" not in propiedades
    # Pero el modelo (lo que persiste y sirve la ficha) sí lo declara.
    assert "senales_no_reconocidas" in AnalisisCualitativo.model_fields
