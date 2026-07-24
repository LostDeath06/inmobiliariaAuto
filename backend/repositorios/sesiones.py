"""Última foto contabilizada de cada sesión de conversación de OpenClaw.

Existe por una razón concreta: el fichero .jsonl de una sesión ACUMULA. Cada
lectura ve el total de siempre, no lo nuevo. Sin recordar lo ya anotado, cada
pasada del worker volvería a sumar la sesión entera y el gasto se multiplicaría
por el número de lecturas. Aquí se guarda la foto anterior; al libro solo va la
diferencia.
"""

from __future__ import annotations

from ..nucleo import basedatos

_COLUMNAS = """
    id, agente, modelo, tokens_entrada, tokens_salida, tokens_cache_write,
    tokens_cache_read, turnos, tokens_proximo_mensaje, bytes, modificada_en, leida_en
"""


async def obtener(sesion_id: str) -> dict | None:
    fila = await basedatos.obtener_uno(
        f"SELECT {_COLUMNAS} FROM sesiones_openclaw WHERE id = $1", sesion_id
    )
    return dict(fila) if fila else None


async def listar() -> list[dict]:
    """Las que más cuestan por mensaje primero: son las que hay que limpiar."""
    filas = await basedatos.obtener_todos(
        f"SELECT {_COLUMNAS} FROM sesiones_openclaw ORDER BY tokens_proximo_mensaje DESC"
    )
    return [dict(f) for f in filas]


async def guardar(
    *, sesion_id: str, agente: str | None, modelo: str | None,
    entrada: int, salida: int, cache_write: int, cache_read: int,
    turnos: int, tokens_proximo_mensaje: int, bytes_: int, modificada_en,
) -> None:
    """Fija la nueva foto. Lo que aquí queda es «lo ya contabilizado»."""
    await basedatos.ejecutar(
        """
        INSERT INTO sesiones_openclaw
            (id, agente, modelo, tokens_entrada, tokens_salida, tokens_cache_write,
             tokens_cache_read, turnos, tokens_proximo_mensaje, bytes, modificada_en, leida_en)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11, now())
        ON CONFLICT (id) DO UPDATE SET
            agente = EXCLUDED.agente,
            modelo = COALESCE(EXCLUDED.modelo, sesiones_openclaw.modelo),
            tokens_entrada = EXCLUDED.tokens_entrada,
            tokens_salida = EXCLUDED.tokens_salida,
            tokens_cache_write = EXCLUDED.tokens_cache_write,
            tokens_cache_read = EXCLUDED.tokens_cache_read,
            turnos = EXCLUDED.turnos,
            tokens_proximo_mensaje = EXCLUDED.tokens_proximo_mensaje,
            bytes = EXCLUDED.bytes,
            modificada_en = EXCLUDED.modificada_en,
            leida_en = now()
        """,
        sesion_id, agente, modelo, entrada, salida, cache_write, cache_read,
        turnos, tokens_proximo_mensaje, bytes_, modificada_en,
    )
