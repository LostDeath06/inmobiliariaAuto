"""Repositorio del libro de gasto y de los precios por modelo."""

from __future__ import annotations

import json
from decimal import Decimal
from uuid import UUID

from ..modelos.costes import PrecioModelo, UsoTokens
from ..nucleo import basedatos
from .base import a_modelo, a_modelos

_COL_PRECIO = """
    modelo, usd_entrada_por_m, usd_salida_por_m, usd_cache_write_por_m,
    usd_cache_read_por_m, fuente, updated_at
"""

_COL_USO = """
    id, fuente, modelo, job_id, inmueble_id, tokens_entrada, tokens_salida,
    tokens_cache_write, tokens_cache_read, coste_usd, detalle, created_at
"""


# --- Precios -----------------------------------------------------------------


async def listar_precios() -> list[PrecioModelo]:
    filas = await basedatos.obtener_todos(
        f"SELECT {_COL_PRECIO} FROM precios_modelo ORDER BY modelo"
    )
    return a_modelos(filas, PrecioModelo)


async def obtener_precio(modelo: str) -> PrecioModelo | None:
    fila = await basedatos.obtener_uno(
        f"SELECT {_COL_PRECIO} FROM precios_modelo WHERE modelo = $1", modelo
    )
    return a_modelo(fila, PrecioModelo)


async def establecer_precio(
    *, modelo: str, entrada: Decimal, salida: Decimal,
    cache_write: Decimal, cache_read: Decimal, fuente: str | None,
) -> PrecioModelo:
    fila = await basedatos.obtener_uno(
        f"""
        INSERT INTO precios_modelo
            (modelo, usd_entrada_por_m, usd_salida_por_m, usd_cache_write_por_m,
             usd_cache_read_por_m, fuente)
        VALUES ($1,$2,$3,$4,$5,$6)
        ON CONFLICT (modelo) DO UPDATE SET
            usd_entrada_por_m = EXCLUDED.usd_entrada_por_m,
            usd_salida_por_m = EXCLUDED.usd_salida_por_m,
            usd_cache_write_por_m = EXCLUDED.usd_cache_write_por_m,
            usd_cache_read_por_m = EXCLUDED.usd_cache_read_por_m,
            fuente = EXCLUDED.fuente
        RETURNING {_COL_PRECIO}
        """,
        modelo, entrada, salida, cache_write, cache_read, fuente,
    )
    return a_modelo(fila, PrecioModelo)  # type: ignore[return-value]


# --- Libro de uso ------------------------------------------------------------


async def registrar(uso: UsoTokens) -> None:
    """Anota una llamada facturable. Nunca falla el flujo que la origina:
    perder una anotación de coste es malo, pero perder el análisis es peor."""
    await basedatos.ejecutar(
        """
        INSERT INTO uso_tokens
            (fuente, modelo, job_id, inmueble_id, tokens_entrada, tokens_salida,
             tokens_cache_write, tokens_cache_read, coste_usd, detalle)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        """,
        uso.fuente.value, uso.modelo, uso.job_id, uso.inmueble_id,
        uso.tokens_entrada, uso.tokens_salida, uso.tokens_cache_write,
        uso.tokens_cache_read, uso.coste_usd, json.dumps(uso.detalle or {}),
    )


_SUMA = """
    COALESCE(SUM(tokens_entrada),0)      AS tokens_entrada,
    COALESCE(SUM(tokens_salida),0)       AS tokens_salida,
    COALESCE(SUM(tokens_cache_write),0)  AS tokens_cache_write,
    COALESCE(SUM(tokens_cache_read),0)   AS tokens_cache_read,
    COALESCE(SUM(coste_usd),0)           AS coste_usd,
    COUNT(*)                             AS llamadas
"""


async def total() -> dict:
    fila = await basedatos.obtener_uno(f"SELECT {_SUMA} FROM uso_tokens")
    return dict(fila) if fila else {}


async def por_fuente() -> list[dict]:
    filas = await basedatos.obtener_todos(
        f"SELECT fuente::text AS fuente, {_SUMA} FROM uso_tokens GROUP BY fuente ORDER BY coste_usd DESC"
    )
    return [dict(f) for f in filas]


async def por_dia(dias: int = 30) -> list[dict]:
    filas = await basedatos.obtener_todos(
        f"""
        SELECT (created_at AT TIME ZONE 'UTC')::date AS dia, fuente::text AS fuente, {_SUMA}
        FROM uso_tokens
        WHERE created_at >= now() - ($1::int * INTERVAL '1 day')
        GROUP BY 1, 2
        ORDER BY 1 DESC, 2
        """,
        dias,
    )
    return [dict(f) for f in filas]


async def por_job(limite: int = 50) -> list[dict]:
    filas = await basedatos.obtener_todos(
        f"""
        SELECT u.job_id, {_SUMA},
               MIN(u.created_at) AS desde, j.estado::text AS estado
        FROM uso_tokens u
        LEFT JOIN jobs j ON j.id = u.job_id
        WHERE u.job_id IS NOT NULL
        GROUP BY u.job_id, j.estado
        ORDER BY MIN(u.created_at) DESC
        LIMIT $1
        """,
        limite,
    )
    return [dict(f) for f in filas]


async def por_inmueble(limite: int = 50) -> list[dict]:
    filas = await basedatos.obtener_todos(
        f"""
        SELECT u.inmueble_id, {_SUMA}, i.titulo, i.ciudad, i.pais
        FROM uso_tokens u
        LEFT JOIN inmuebles i ON i.id = u.inmueble_id
        WHERE u.inmueble_id IS NOT NULL
        GROUP BY u.inmueble_id, i.titulo, i.ciudad, i.pais
        ORDER BY SUM(u.coste_usd) DESC
        LIMIT $1
        """,
        limite,
    )
    return [dict(f) for f in filas]


async def gasto_de_hoy() -> Decimal:
    fila = await basedatos.obtener_uno(
        "SELECT COALESCE(SUM(coste_usd),0) AS c FROM uso_tokens "
        "WHERE created_at >= date_trunc('day', now())"
    )
    return Decimal(str(fila["c"])) if fila else Decimal(0)


async def listar(limite: int = 100) -> list[UsoTokens]:
    filas = await basedatos.obtener_todos(
        f"SELECT {_COL_USO} FROM uso_tokens ORDER BY created_at DESC LIMIT $1", limite
    )
    return a_modelos(filas, UsoTokens)


async def por_job_id(job_id: UUID) -> Decimal:
    """Coste acumulado de un job concreto, leído del libro (no recalculado)."""
    fila = await basedatos.obtener_uno(
        "SELECT COALESCE(SUM(coste_usd),0) AS c FROM uso_tokens WHERE job_id = $1",
        job_id,
    )
    return Decimal(str(fila["c"])) if fila else Decimal(0)


async def registro_desde():
    """Fecha del primer apunte. El libro empieza cuando se desplegó esta versión:
    el gasto anterior no quedó anotado y no se puede reconstruir. Sin este dato,
    dentro de tres meses «gasto total» se confundiría con «gasto de siempre»."""
    fila = await basedatos.obtener_uno("SELECT MIN(created_at) AS d FROM uso_tokens")
    return fila["d"] if fila else None
