"""Repositorio de búsquedas."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from ..modelos.pipeline import Busqueda
from ..nucleo import basedatos
from .base import a_modelo, a_modelos

_COLUMNAS = """
    id, portal_id, ciudad, presupuesto_min, presupuesto_max, moneda, tipo_inmueble,
    filtros_extra, activa, frecuencia_cron, ultima_ejecucion, proxima_ejecucion,
    propietario_id, created_at, updated_at
"""


async def listar() -> list[Busqueda]:
    return a_modelos(
        await basedatos.obtener_todos(
            f"SELECT {_COLUMNAS} FROM busquedas ORDER BY created_at DESC"
        ),
        Busqueda,
    )


async def obtener(busqueda_id: UUID) -> Busqueda | None:
    fila = await basedatos.obtener_uno(
        f"SELECT {_COLUMNAS} FROM busquedas WHERE id = $1", busqueda_id
    )
    return a_modelo(fila, Busqueda)


async def crear(
    *,
    portal_id: UUID,
    ciudad: str | None,
    presupuesto_min: Decimal | None,
    presupuesto_max: Decimal | None,
    moneda: str | None,
    tipo_inmueble: str | None,
    filtros_extra: dict | None = None,
    frecuencia_cron: str | None = None,
    propietario_id: UUID | None = None,
) -> Busqueda:
    fila = await basedatos.obtener_uno(
        f"""
        INSERT INTO busquedas
            (portal_id, ciudad, presupuesto_min, presupuesto_max, moneda,
             tipo_inmueble, filtros_extra, frecuencia_cron, propietario_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING {_COLUMNAS}
        """,
        portal_id, ciudad, presupuesto_min, presupuesto_max, moneda,
        tipo_inmueble, filtros_extra or {}, frecuencia_cron, propietario_id,
    )
    return a_modelo(fila, Busqueda)  # type: ignore[return-value]


async def marcar_ejecutada(busqueda_id: UUID, proxima_ejecucion) -> None:
    await basedatos.ejecutar(
        "UPDATE busquedas SET ultima_ejecucion = now(), proxima_ejecucion = $2 WHERE id = $1",
        busqueda_id, proxima_ejecucion,
    )


async def listar_pendientes_de_cron() -> list[Busqueda]:
    """Búsquedas activas con cron cuya `proxima_ejecucion` ya venció (worker 7A)."""
    return a_modelos(
        await basedatos.obtener_todos(
            f"""
            SELECT {_COLUMNAS} FROM busquedas
            WHERE activa AND frecuencia_cron IS NOT NULL
              AND (proxima_ejecucion IS NULL OR proxima_ejecucion <= now())
            ORDER BY proxima_ejecucion NULLS FIRST
            """
        ),
        Busqueda,
    )
