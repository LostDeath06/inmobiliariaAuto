"""Repositorio de jobs de scraping."""

from __future__ import annotations

from uuid import UUID

from ..modelos.enumeraciones import EstadoJob
from ..modelos.pipeline import Job
from ..nucleo import basedatos
from .base import a_modelo, a_modelos

_COLUMNAS = """
    id, busqueda_id, estado, prompt_enviado, openclaw_job_id, intentos,
    error_mensaje, tokens_entrada, tokens_salida, coste_estimado_usd,
    total_resultados_detectados, total_anuncios_extraidos, total_anuncios_validos,
    total_anuncios_cuarentena, extraccion_completa, iniciado_en, finalizado_en,
    created_at, updated_at
"""

_ACTUALIZABLES = {
    "estado", "prompt_enviado", "openclaw_job_id", "intentos", "error_mensaje",
    "tokens_entrada", "tokens_salida", "coste_estimado_usd",
    "total_resultados_detectados", "total_anuncios_extraidos",
    "total_anuncios_validos", "total_anuncios_cuarentena", "extraccion_completa",
    "iniciado_en", "finalizado_en",
}


async def listar(estado: EstadoJob | None = None) -> list[Job]:
    if estado:
        filas = await basedatos.obtener_todos(
            f"SELECT {_COLUMNAS} FROM jobs WHERE estado = $1 ORDER BY created_at DESC",
            estado.value,
        )
    else:
        filas = await basedatos.obtener_todos(
            f"SELECT {_COLUMNAS} FROM jobs ORDER BY created_at DESC"
        )
    return a_modelos(filas, Job)


async def obtener(job_id: UUID) -> Job | None:
    fila = await basedatos.obtener_uno(
        f"SELECT {_COLUMNAS} FROM jobs WHERE id = $1", job_id
    )
    return a_modelo(fila, Job)


async def crear(busqueda_id: UUID) -> Job:
    fila = await basedatos.obtener_uno(
        f"INSERT INTO jobs (busqueda_id) VALUES ($1) RETURNING {_COLUMNAS}",
        busqueda_id,
    )
    return a_modelo(fila, Job)  # type: ignore[return-value]


async def actualizar(job_id: UUID, cambios: dict) -> Job | None:
    campos = {k: v for k, v in cambios.items() if k in _ACTUALIZABLES}
    if not campos:
        return await obtener(job_id)
    # Los enums se guardan por su valor.
    valores = [
        v.value if isinstance(v, EstadoJob) else v for v in campos.values()
    ]
    asignaciones = ", ".join(f"{c} = ${i}" for i, c in enumerate(campos, start=2))
    fila = await basedatos.obtener_uno(
        f"UPDATE jobs SET {asignaciones} WHERE id = $1 RETURNING {_COLUMNAS}",
        job_id,
        *valores,
    )
    return a_modelo(fila, Job)


async def incrementar_intentos(job_id: UUID) -> None:
    await basedatos.ejecutar(
        "UPDATE jobs SET intentos = intentos + 1 WHERE id = $1", job_id
    )
