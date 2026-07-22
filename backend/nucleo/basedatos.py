"""Gestión del pool de conexiones a PostgreSQL (asyncpg).

Falla ruidosamente: si no hay conexión, propaga la excepción. Nunca devuelve
datos falsos ni silencia un fallo de BD.
"""

from __future__ import annotations

import json
from typing import Any

import asyncpg

from .config import obtener_config

_pool: asyncpg.Pool | None = None


async def _init_conexion(con: asyncpg.Connection) -> None:
    """Registra JSON/JSONB como codec para trabajar con dicts de Python."""
    await con.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )
    await con.set_type_codec(
        "json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )


async def obtener_pool() -> asyncpg.Pool:
    """Devuelve el pool de conexiones, creándolo la primera vez."""
    global _pool
    if _pool is None:
        cfg = obtener_config()
        _pool = await asyncpg.create_pool(
            dsn=cfg.database_url,
            min_size=cfg.db_pool_min,
            max_size=cfg.db_pool_max,
            init=_init_conexion,
        )
    return _pool


async def cerrar_pool() -> None:
    """Cierra el pool (al apagar la aplicación)."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def ejecutar(consulta: str, *args: Any) -> str:
    pool = await obtener_pool()
    async with pool.acquire() as con:
        return await con.execute(consulta, *args)


async def obtener_uno(consulta: str, *args: Any) -> asyncpg.Record | None:
    pool = await obtener_pool()
    async with pool.acquire() as con:
        return await con.fetchrow(consulta, *args)


async def obtener_todos(consulta: str, *args: Any) -> list[asyncpg.Record]:
    pool = await obtener_pool()
    async with pool.acquire() as con:
        return await con.fetch(consulta, *args)
