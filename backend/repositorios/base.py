"""Utilidades comunes de los repositorios."""

from __future__ import annotations

from typing import TypeVar

import asyncpg
from pydantic import BaseModel

M = TypeVar("M", bound=BaseModel)


def a_modelo(record: asyncpg.Record | None, modelo: type[M]) -> M | None:
    """Convierte una fila de asyncpg en un modelo Pydantic, o None."""
    if record is None:
        return None
    return modelo(**dict(record))


def a_modelos(records: list[asyncpg.Record], modelo: type[M]) -> list[M]:
    """Convierte una lista de filas en modelos Pydantic."""
    return [modelo(**dict(r)) for r in records]
