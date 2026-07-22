"""Repositorio de países."""

from __future__ import annotations

from ..modelos.configuracion import Pais
from ..nucleo import basedatos
from .base import a_modelos


async def listar() -> list[Pais]:
    filas = await basedatos.obtener_todos(
        "SELECT codigo, nombre FROM paises ORDER BY nombre"
    )
    return a_modelos(filas, Pais)
