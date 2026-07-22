"""Repositorio de análisis cualitativos (salida de Claude)."""

from __future__ import annotations

from uuid import UUID

from ..modelos.analisis import AnalisisCualitativo
from ..nucleo import basedatos

_COL_LECTURA = """
    estado_conservacion, nivel_reforma_estimado, tipologia, senales_riesgo,
    senales_oportunidad, senales_no_reconocidas, apto_alquiler_larga_estancia,
    apto_alquiler_turistico, potencial_division_horizontal, calidad_descripcion,
    coherencia_precio_descripcion, resumen_analista, banderas_rojas_texto,
    nivel_confianza, campos_no_inferibles
"""


async def obtener(inmueble_id: UUID) -> AnalisisCualitativo | None:
    """Devuelve el análisis como modelo, o None si no existe o falló."""
    fila = await basedatos.obtener_uno(
        f"SELECT {_COL_LECTURA} FROM analisis_cualitativos "
        f"WHERE inmueble_id = $1 AND NOT analisis_fallido",
        inmueble_id,
    )
    if fila is None:
        return None
    datos = dict(fila)
    if datos.get("resumen_analista") is None:
        datos["resumen_analista"] = ""
    return AnalisisCualitativo(**datos)

_COLUMNAS = """
    inmueble_id, hash_contenido, estado_conservacion, nivel_reforma_estimado,
    tipologia, senales_riesgo, senales_oportunidad, senales_no_reconocidas,
    apto_alquiler_larga_estancia, apto_alquiler_turistico,
    potencial_division_horizontal, calidad_descripcion, coherencia_precio_descripcion,
    resumen_analista, banderas_rojas_texto, nivel_confianza, campos_no_inferibles,
    analisis_fallido, modelo
"""


async def guardar(
    inmueble_id: UUID,
    analisis: AnalisisCualitativo,
    *,
    hash_contenido: str | None,
    modelo: str,
) -> None:
    """Inserta o actualiza el análisis del inmueble (uno por inmueble).

    Las `senales_*` son `list[str]` (códigos del catálogo, no enums): se pasan tal
    cual a los arrays TEXT[] de Postgres.
    """
    await basedatos.ejecutar(
        f"""
        INSERT INTO analisis_cualitativos ({_COLUMNAS})
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19)
        ON CONFLICT (inmueble_id) DO UPDATE SET
            hash_contenido = EXCLUDED.hash_contenido,
            estado_conservacion = EXCLUDED.estado_conservacion,
            nivel_reforma_estimado = EXCLUDED.nivel_reforma_estimado,
            tipologia = EXCLUDED.tipologia,
            senales_riesgo = EXCLUDED.senales_riesgo,
            senales_oportunidad = EXCLUDED.senales_oportunidad,
            senales_no_reconocidas = EXCLUDED.senales_no_reconocidas,
            apto_alquiler_larga_estancia = EXCLUDED.apto_alquiler_larga_estancia,
            apto_alquiler_turistico = EXCLUDED.apto_alquiler_turistico,
            potencial_division_horizontal = EXCLUDED.potencial_division_horizontal,
            calidad_descripcion = EXCLUDED.calidad_descripcion,
            coherencia_precio_descripcion = EXCLUDED.coherencia_precio_descripcion,
            resumen_analista = EXCLUDED.resumen_analista,
            banderas_rojas_texto = EXCLUDED.banderas_rojas_texto,
            nivel_confianza = EXCLUDED.nivel_confianza,
            campos_no_inferibles = EXCLUDED.campos_no_inferibles,
            analisis_fallido = EXCLUDED.analisis_fallido,
            modelo = EXCLUDED.modelo
        """,
        inmueble_id,
        hash_contenido,
        analisis.estado_conservacion.value,
        analisis.nivel_reforma_estimado.value,
        analisis.tipologia.value,
        analisis.senales_riesgo,
        analisis.senales_oportunidad,
        analisis.senales_no_reconocidas,
        analisis.apto_alquiler_larga_estancia.value,
        analisis.apto_alquiler_turistico.value,
        analisis.potencial_division_horizontal.value,
        analisis.calidad_descripcion.value,
        analisis.coherencia_precio_descripcion.value,
        analisis.resumen_analista,
        analisis.banderas_rojas_texto,
        analisis.nivel_confianza.value,
        analisis.campos_no_inferibles,
        False,
        modelo,
    )


async def marcar_fallido(inmueble_id: UUID, modelo: str) -> None:
    """Marca el inmueble como ANALISIS_FALLIDO sin abortar el lote (§8.1)."""
    await basedatos.ejecutar(
        """
        INSERT INTO analisis_cualitativos (inmueble_id, analisis_fallido, modelo)
        VALUES ($1, TRUE, $2)
        ON CONFLICT (inmueble_id) DO UPDATE SET analisis_fallido = TRUE
        """,
        inmueble_id,
        modelo,
    )


async def obtener_hash(inmueble_id: UUID) -> str | None:
    """Devuelve el hash del último análisis, para cachear (§8.4)."""
    fila = await basedatos.obtener_uno(
        "SELECT hash_contenido FROM analisis_cualitativos WHERE inmueble_id = $1",
        inmueble_id,
    )
    return fila["hash_contenido"] if fila else None


async def listar_senales_no_reconocidas() -> list[dict]:
    """Inmuebles cuyo análisis trae códigos fuera del catálogo del país.

    Cola de revisión del monitor: cada fila es un caso a mirar (o Claude alucinó un
    código, o falta ese código en el catálogo de ese país). Nunca se pierde: si está
    aquí, el propietario lo ve.
    """
    filas = await basedatos.obtener_todos(
        """
        SELECT a.inmueble_id, a.senales_no_reconocidas,
               i.titulo, i.ciudad, i.pais, i.url_anuncio
        FROM analisis_cualitativos a
        JOIN inmuebles i ON i.id = a.inmueble_id
        WHERE array_length(a.senales_no_reconocidas, 1) > 0
        ORDER BY i.pais, i.ciudad
        """
    )
    return [dict(f) for f in filas]
