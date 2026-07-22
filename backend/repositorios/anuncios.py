"""Repositorio de anuncios crudos (inmutable) y cuarentena (2A)."""

from __future__ import annotations

from uuid import UUID

from ..modelos.pipeline import AnuncioCrudoRegistro, AnuncioCuarentena
from ..nucleo import basedatos
from .base import a_modelo, a_modelos

_COL_CRUDO = "id, job_id, url_anuncio, payload_json, hash_contenido, created_at"
_COL_CUARENTENA = "id, job_id, url_anuncio, payload_crudo, errores_validacion, created_at"


# --- Anuncios crudos (append-only) -------------------------------------------


async def guardar_crudo(
    *, job_id: UUID, url_anuncio: str, payload_json: dict, hash_contenido: str
) -> AnuncioCrudoRegistro:
    fila = await basedatos.obtener_uno(
        f"""
        INSERT INTO anuncios_crudos (job_id, url_anuncio, payload_json, hash_contenido)
        VALUES ($1, $2, $3, $4)
        RETURNING {_COL_CRUDO}
        """,
        job_id,
        url_anuncio,
        payload_json,
        hash_contenido,
    )
    return a_modelo(fila, AnuncioCrudoRegistro)  # type: ignore[return-value]


async def listar_crudos_de_job(job_id: UUID) -> list[AnuncioCrudoRegistro]:
    filas = await basedatos.obtener_todos(
        f"SELECT {_COL_CRUDO} FROM anuncios_crudos WHERE job_id = $1 ORDER BY created_at",
        job_id,
    )
    return a_modelos(filas, AnuncioCrudoRegistro)


# --- Cuarentena --------------------------------------------------------------


async def guardar_en_cuarentena(
    *,
    job_id: UUID,
    url_anuncio: str | None,
    payload_crudo: dict,
    errores_validacion: list[dict],
) -> AnuncioCuarentena:
    fila = await basedatos.obtener_uno(
        f"""
        INSERT INTO anuncios_cuarentena
            (job_id, url_anuncio, payload_crudo, errores_validacion)
        VALUES ($1, $2, $3, $4)
        RETURNING {_COL_CUARENTENA}
        """,
        job_id,
        url_anuncio,
        payload_crudo,
        errores_validacion,
    )
    return a_modelo(fila, AnuncioCuarentena)  # type: ignore[return-value]


async def listar_cuarentena_de_job(job_id: UUID) -> list[AnuncioCuarentena]:
    """Anuncios en cuarentena de un job. Se muestra en el monitor de jobs (2A)."""
    filas = await basedatos.obtener_todos(
        f"SELECT {_COL_CUARENTENA} FROM anuncios_cuarentena WHERE job_id = $1 "
        f"ORDER BY created_at",
        job_id,
    )
    return a_modelos(filas, AnuncioCuarentena)
