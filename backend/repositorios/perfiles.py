"""Repositorio de perfiles de inversor."""

from __future__ import annotations

from uuid import UUID

from ..modelos.configuracion import PerfilInversor
from ..nucleo import basedatos
from .base import a_modelo, a_modelos

_COLUMNAS = """
    id, nombre, descripcion, activo, es_predeterminado, pesos, supuestos,
    propietario_id, created_at, updated_at
"""


async def listar(solo_activos: bool = False) -> list[PerfilInversor]:
    consulta = f"SELECT {_COLUMNAS} FROM perfiles_inversor"
    if solo_activos:
        consulta += " WHERE activo"
    consulta += " ORDER BY nombre"
    return a_modelos(await basedatos.obtener_todos(consulta), PerfilInversor)


async def obtener(perfil_id: UUID) -> PerfilInversor | None:
    fila = await basedatos.obtener_uno(
        f"SELECT {_COLUMNAS} FROM perfiles_inversor WHERE id = $1", perfil_id
    )
    return a_modelo(fila, PerfilInversor)


async def obtener_predeterminado() -> PerfilInversor | None:
    fila = await basedatos.obtener_uno(
        f"SELECT {_COLUMNAS} FROM perfiles_inversor "
        f"WHERE es_predeterminado AND activo LIMIT 1"
    )
    return a_modelo(fila, PerfilInversor)


async def crear(
    *,
    nombre: str,
    descripcion: str | None,
    pesos: dict,
    supuestos: dict,
    es_predeterminado: bool = False,
    activo: bool = True,
    propietario_id: UUID | None = None,
) -> PerfilInversor:
    fila = await basedatos.obtener_uno(
        f"""
        INSERT INTO perfiles_inversor
            (nombre, descripcion, pesos, supuestos, es_predeterminado, activo, propietario_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        RETURNING {_COLUMNAS}
        """,
        nombre, descripcion, pesos, supuestos, es_predeterminado, activo, propietario_id,
    )
    return a_modelo(fila, PerfilInversor)  # type: ignore[return-value]


async def actualizar(perfil_id: UUID, cambios: dict) -> PerfilInversor | None:
    permitidas = {
        "nombre", "descripcion", "activo", "es_predeterminado", "pesos", "supuestos",
    }
    campos = {k: v for k, v in cambios.items() if k in permitidas}
    if not campos:
        return await obtener(perfil_id)
    asignaciones = ", ".join(f"{c} = ${i}" for i, c in enumerate(campos, start=2))
    fila = await basedatos.obtener_uno(
        f"UPDATE perfiles_inversor SET {asignaciones} WHERE id = $1 RETURNING {_COLUMNAS}",
        perfil_id, *campos.values(),
    )
    return a_modelo(fila, PerfilInversor)


async def eliminar(perfil_id: UUID) -> bool:
    resultado = await basedatos.ejecutar(
        "DELETE FROM perfiles_inversor WHERE id = $1", perfil_id
    )
    return resultado.endswith("1")
