"""Repositorio de scores. Clave compuesta (inmueble_id, perfil_id)."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from ..modelos.enumeraciones import CalidadDato
from ..modelos.score import Score
from ..nucleo import basedatos
from .base import a_modelo, a_modelos

_COLUMNAS = """
    inmueble_id, perfil_id, score_bruto, score_total, riesgo_pais_aplicado, desglose,
    estado_calidad, motivo_descarte, usa_parametros_provisionales, obsoleto,
    version_pesos, calculado_en
"""


async def guardar(
    *,
    inmueble_id: UUID,
    perfil_id: UUID,
    score_bruto: Decimal | None,
    score_total: Decimal | None,
    riesgo_pais_aplicado: Decimal | None,
    desglose: dict,
    estado_calidad: CalidadDato,
    motivo_descarte: list[str],
    usa_parametros_provisionales: bool,
    version_pesos: str | None,
) -> Score:
    fila = await basedatos.obtener_uno(
        f"""
        INSERT INTO scores
            (inmueble_id, perfil_id, score_bruto, score_total, riesgo_pais_aplicado,
             desglose, estado_calidad, motivo_descarte, usa_parametros_provisionales,
             obsoleto, version_pesos, calculado_en)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,FALSE,$10, now())
        ON CONFLICT (inmueble_id, perfil_id) DO UPDATE SET
            score_bruto = EXCLUDED.score_bruto,
            score_total = EXCLUDED.score_total,
            riesgo_pais_aplicado = EXCLUDED.riesgo_pais_aplicado,
            desglose = EXCLUDED.desglose,
            estado_calidad = EXCLUDED.estado_calidad,
            motivo_descarte = EXCLUDED.motivo_descarte,
            usa_parametros_provisionales = EXCLUDED.usa_parametros_provisionales,
            obsoleto = FALSE,
            version_pesos = EXCLUDED.version_pesos,
            calculado_en = now()
        RETURNING {_COLUMNAS}
        """,
        inmueble_id, perfil_id, score_bruto, score_total, riesgo_pais_aplicado,
        desglose, estado_calidad.value, motivo_descarte, usa_parametros_provisionales,
        version_pesos,
    )
    return a_modelo(fila, Score)  # type: ignore[return-value]


async def marcar_obsoletos_de_perfil(perfil_id: UUID) -> int:
    """Marca todos los scores de un perfil como obsoletos (tras cambiar pesos, §9)."""
    resultado = await basedatos.ejecutar(
        "UPDATE scores SET obsoleto = TRUE WHERE perfil_id = $1 AND NOT obsoleto",
        perfil_id,
    )
    return int(resultado.split()[-1]) if resultado else 0


async def ranking(
    perfil_id: UUID,
    *,
    pais: str | None = None,
    sin_riesgo_pais: bool = False,
    limite: int = 50,
    incluir_obsoletos: bool = False,
) -> list[dict]:
    """Top-N para un perfil.

    - `pais`: filtro por país (salvaguarda 1). None = ranking global.
    - `sin_riesgo_pais`: ordena por `score_bruto` en vez de `score_total`
      (salvaguarda 2: ver scores brutos, sin el multiplicador de riesgo país).

    Excluye NO_CALCULABLE y DESCARTADO_RIESGO del ranking activo. Devuelve dicts
    con el score + datos del inmueble para la tabla del ranking.
    """
    columna_orden = "s.score_bruto" if sin_riesgo_pais else "s.score_total"
    condiciones = ["s.perfil_id = $1", f"{columna_orden} IS NOT NULL",
                   "s.estado_calidad NOT IN ('NO_CALCULABLE','DESCARTADO_RIESGO')"]
    args: list = [perfil_id]
    if not incluir_obsoletos:
        condiciones.append("NOT s.obsoleto")
    if pais:
        args.append(pais)
        condiciones.append(f"i.pais = ${len(args)}")
    args.append(limite)
    filas = await basedatos.obtener_todos(
        f"""
        SELECT s.inmueble_id, s.perfil_id, s.score_bruto, s.score_total,
               s.riesgo_pais_aplicado, s.estado_calidad, s.usa_parametros_provisionales,
               s.obsoleto, s.desglose,
               i.titulo, i.precio, i.moneda, i.ciudad, i.pais, i.url_anuncio,
               i.superficie_util_m2, i.superficie_construida_m2,
               i.posible_duplicado_cross_portal, i.tiene_confotur,
               z.perfil_zona
        FROM scores s JOIN inmuebles i ON i.id = s.inmueble_id
        -- Perfil de la zona (turística/estándar) para marcarlo en el ranking. Prioriza
        -- el benchmark de barrio; si no hay, cae al de ciudad (barrio NULL).
        LEFT JOIN LATERAL (
            SELECT b.perfil_zona FROM benchmarks_zona b
            WHERE b.pais = i.pais AND b.ciudad = i.ciudad
              AND (b.barrio = i.barrio OR b.barrio IS NULL)
            ORDER BY (b.barrio = i.barrio) DESC NULLS LAST
            LIMIT 1
        ) z ON TRUE
        WHERE {' AND '.join(condiciones)}
        ORDER BY {columna_orden} DESC
        LIMIT ${len(args)}
        """,
        *args,
    )
    return [dict(f) for f in filas]


async def obtener(inmueble_id: UUID, perfil_id: UUID) -> Score | None:
    fila = await basedatos.obtener_uno(
        f"SELECT {_COLUMNAS} FROM scores WHERE inmueble_id = $1 AND perfil_id = $2",
        inmueble_id, perfil_id,
    )
    return a_modelo(fila, Score)


async def listar_por_inmueble(inmueble_id: UUID) -> list[Score]:
    """Todos los scores de un inmueble (uno por perfil): cashflow vs plusvalía."""
    return a_modelos(
        await basedatos.obtener_todos(
            f"SELECT {_COLUMNAS} FROM scores WHERE inmueble_id = $1", inmueble_id
        ),
        Score,
    )
