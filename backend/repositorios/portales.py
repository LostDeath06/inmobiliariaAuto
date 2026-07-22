"""Repositorio de portales."""

from __future__ import annotations

from uuid import UUID

from ..modelos.configuracion import Portal
from ..nucleo import basedatos
from .base import a_modelo, a_modelos

_COLUMNAS = """
    id, nombre, url_raiz, pais, activo, notas_extraccion,
    tasa_exito_historica, propietario_id, created_at, updated_at
"""


async def listar(solo_activos: bool = False) -> list[Portal]:
    consulta = f"SELECT {_COLUMNAS} FROM portales"
    if solo_activos:
        consulta += " WHERE activo"
    consulta += " ORDER BY nombre"
    return a_modelos(await basedatos.obtener_todos(consulta), Portal)


async def listar_por_pais(pais: str) -> list[Portal]:
    """Todos los portales de un país, activos e inactivos. Los inactivos con notas
    dejan registrado (p. ej.) que un portal bloquea el acceso automatizado."""
    return a_modelos(
        await basedatos.obtener_todos(
            f"SELECT {_COLUMNAS} FROM portales WHERE pais = $1 ORDER BY activo DESC, nombre",
            pais,
        ),
        Portal,
    )


async def obtener(portal_id: UUID) -> Portal | None:
    fila = await basedatos.obtener_uno(
        f"SELECT {_COLUMNAS} FROM portales WHERE id = $1", portal_id
    )
    return a_modelo(fila, Portal)


async def crear(
    *,
    nombre: str,
    url_raiz: str,
    pais: str | None = None,
    notas_extraccion: str | None = None,
    propietario_id: UUID | None = None,
) -> Portal:
    fila = await basedatos.obtener_uno(
        f"""
        INSERT INTO portales (nombre, url_raiz, pais, notas_extraccion, propietario_id)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING {_COLUMNAS}
        """,
        nombre,
        url_raiz,
        pais,
        notas_extraccion,
        propietario_id,
    )
    return a_modelo(fila, Portal)  # type: ignore[return-value]
