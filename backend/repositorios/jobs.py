"""Repositorio de jobs de scraping."""

from __future__ import annotations

from uuid import UUID

from ..modelos.enumeraciones import EstadoJob
from ..modelos.pipeline import Job
from ..nucleo import basedatos
from .base import a_modelo, a_modelos

_COLUMNAS = """
    id, busqueda_id, estado, prompt_enviado, openclaw_job_id, intentos,
    sondeos_no_encontrado, error_mensaje, tokens_entrada, tokens_salida,
    coste_estimado_usd,
    total_resultados_detectados, total_anuncios_extraidos, total_anuncios_validos,
    total_anuncios_cuarentena, extraccion_completa, iniciado_en, finalizado_en,
    created_at, updated_at
"""

_ACTUALIZABLES = {
    "estado", "prompt_enviado", "openclaw_job_id", "intentos",
    "sondeos_no_encontrado", "error_mensaje",
    "tokens_entrada", "tokens_salida", "coste_estimado_usd",
    "total_resultados_detectados", "total_anuncios_extraidos",
    "total_anuncios_validos", "total_anuncios_cuarentena", "extraccion_completa",
    "iniciado_en", "finalizado_en",
}

# Un job en cualquiera de estos estados todavía "espera algo". Son los únicos
# que pueden quedarse colgados, y por tanto los únicos que hay que vigilar.
ESTADOS_VIVOS = ("PENDIENTE", "ENVIADO", "EN_PROGRESO")


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


async def listar_vivos() -> list[Job]:
    """Jobs que aún esperan algo. Son los que pueden quedarse colgados."""
    # `estado::text` y no un cast a estado_job[]: el resto del repositorio ya
    # trata el enum como texto al escribir, y así no depende del codec de enums.
    filas = await basedatos.obtener_todos(
        f"SELECT {_COLUMNAS} FROM jobs WHERE estado::text = ANY($1::text[]) "
        "ORDER BY created_at",
        list(ESTADOS_VIVOS),
    )
    return a_modelos(filas, Job)


async def contar_sondeo_no_encontrado(job_id: UUID) -> int:
    """Suma uno al contador de 404 seguidos y devuelve el nuevo valor."""
    fila = await basedatos.obtener_uno(
        "UPDATE jobs SET sondeos_no_encontrado = sondeos_no_encontrado + 1 "
        "WHERE id = $1 RETURNING sondeos_no_encontrado",
        job_id,
    )
    return int(fila["sondeos_no_encontrado"]) if fila else 0


async def reiniciar_sondeo_no_encontrado(job_id: UUID) -> None:
    """El adaptador volvió a reconocer el job: el contador vuelve a cero.

    Son 404 SEGUIDOS, no acumulados de por vida. Un reinicio del adaptador entre
    dos jobs sanos no debe acercar al siguiente a la muerte.
    """
    await basedatos.ejecutar(
        "UPDATE jobs SET sondeos_no_encontrado = 0 "
        "WHERE id = $1 AND sondeos_no_encontrado <> 0",
        job_id,
    )


async def cerrar(job_id: UUID, estado: str, motivo: str) -> Job | None:
    """Cierra un job con su motivo y su hora de fin.

    Todo cierre pasa por aquí para que ninguno se quede sin `finalizado_en`: sin
    esa marca no se puede distinguir un job que terminó de uno que se colgó.
    """
    fila = await basedatos.obtener_uno(
        f"UPDATE jobs SET estado = $2, error_mensaje = $3, "
        f"finalizado_en = COALESCE(finalizado_en, now()) "
        f"WHERE id = $1 RETURNING {_COLUMNAS}",
        job_id, estado, motivo,
    )
    return a_modelo(fila, Job)


async def cerrar_zombis(minutos: int) -> list[Job]:
    """Cierra como FALLIDO los jobs vivos parados desde hace más de `minutos`.

    La limpieza manual del ruido que ya existe: jobs de antes de que hubiera
    timeout, que el adaptador olvidó al reiniciarse y que nadie va a resolver.
    """
    filas = await basedatos.obtener_todos(
        f"""
        UPDATE jobs SET
            estado = 'FALLIDO',
            finalizado_en = COALESCE(finalizado_en, now()),
            error_mensaje = COALESCE(error_mensaje || E'\\n', '') ||
                'Cerrado en la limpieza manual de jobs zombis: llevaba más de '
                || $1::text || ' minutos sin avanzar y el adaptador no lo reconoce.'
        WHERE estado::text = ANY($2::text[])
          AND COALESCE(iniciado_en, created_at) < now() - ($1::int * INTERVAL '1 minute')
        RETURNING {_COLUMNAS}
        """,
        minutos, list(ESTADOS_VIVOS),
    )
    return a_modelos(filas, Job)
