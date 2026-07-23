"""Repositorio de inmuebles e histórico de precios (multi-divisa)."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from ..modelos.pipeline import HistoricoPrecio, Inmueble
from ..nucleo import basedatos
from .base import a_modelo, a_modelos

_COLUMNAS = """
    id, portal_id, id_portal, url_anuncio, hash_deduplicacion, titulo, precio, moneda,
    superficie_construida_m2, superficie_util_m2, habitaciones, banos, planta,
    tiene_ascensor, ano_construccion, certificado_energetico, direccion_texto, barrio,
    ciudad, provincia, pais, codigo_postal, latitud, longitud, descripcion_completa,
    caracteristicas_listadas, urls_imagenes, tipo_anunciante, fecha_publicacion,
    gastos_comunidad_mes, estado_calidad, tiene_confotur,
    posible_duplicado_cross_portal,
    inmuebles_duplicados_ids, primer_visto, ultimo_visto, propietario_id,
    created_at, updated_at
"""

_ESCRIBIBLES = {
    "portal_id", "id_portal", "url_anuncio", "hash_deduplicacion", "titulo", "precio",
    "moneda", "superficie_construida_m2", "superficie_util_m2", "habitaciones", "banos",
    "planta", "tiene_ascensor", "ano_construccion", "certificado_energetico",
    "direccion_texto", "barrio", "ciudad", "provincia", "pais", "codigo_postal",
    "latitud", "longitud", "descripcion_completa", "caracteristicas_listadas",
    "urls_imagenes", "tipo_anunciante", "fecha_publicacion", "gastos_comunidad_mes",
    "estado_calidad", "propietario_id",
    # Lo fija el propietario desde la ficha. La ingesta NUNCA lo manda, así que
    # reingestar el mismo anuncio no borra lo que el propietario haya confirmado.
    "tiene_confotur",
}


async def obtener(inmueble_id: UUID) -> Inmueble | None:
    fila = await basedatos.obtener_uno(
        f"SELECT {_COLUMNAS} FROM inmuebles WHERE id = $1", inmueble_id
    )
    return a_modelo(fila, Inmueble)


async def obtener_por_hash(portal_id: UUID, hash_deduplicacion: str) -> Inmueble | None:
    fila = await basedatos.obtener_uno(
        f"SELECT {_COLUMNAS} FROM inmuebles WHERE portal_id = $1 AND hash_deduplicacion = $2",
        portal_id, hash_deduplicacion,
    )
    return a_modelo(fila, Inmueble)


async def listar(
    *,
    pais: str | None = None,
    ciudad: str | None = None,
    precio_min: Decimal | None = None,
    precio_max: Decimal | None = None,
    limite: int = 100,
    desplazamiento: int = 0,
) -> list[Inmueble]:
    condiciones, args = [], []
    if pais:
        args.append(pais)
        condiciones.append(f"pais = ${len(args)}")
    if ciudad:
        args.append(ciudad)
        condiciones.append(f"ciudad = ${len(args)}")
    if precio_min is not None:
        args.append(precio_min)
        condiciones.append(f"precio >= ${len(args)}")
    if precio_max is not None:
        args.append(precio_max)
        condiciones.append(f"precio <= ${len(args)}")
    where = f" WHERE {' AND '.join(condiciones)}" if condiciones else ""
    args.append(limite)
    args.append(desplazamiento)
    filas = await basedatos.obtener_todos(
        f"SELECT {_COLUMNAS} FROM inmuebles{where} "
        f"ORDER BY ultimo_visto DESC LIMIT ${len(args) - 1} OFFSET ${len(args)}",
        *args,
    )
    return a_modelos(filas, Inmueble)


async def insertar(datos: dict) -> Inmueble:
    campos = {k: v for k, v in datos.items() if k in _ESCRIBIBLES}
    columnas = ", ".join(campos)
    marcadores = ", ".join(f"${i}" for i in range(1, len(campos) + 1))
    fila = await basedatos.obtener_uno(
        f"INSERT INTO inmuebles ({columnas}) VALUES ({marcadores}) RETURNING {_COLUMNAS}",
        *campos.values(),
    )
    return a_modelo(fila, Inmueble)  # type: ignore[return-value]


async def actualizar(inmueble_id: UUID, cambios: dict) -> Inmueble | None:
    campos = {k: v for k, v in cambios.items() if k in _ESCRIBIBLES}
    asignaciones = [f"{c} = ${i}" for i, c in enumerate(campos, start=2)]
    asignaciones.append("ultimo_visto = now()")
    fila = await basedatos.obtener_uno(
        f"UPDATE inmuebles SET {', '.join(asignaciones)} WHERE id = $1 RETURNING {_COLUMNAS}",
        inmueble_id, *campos.values(),
    )
    return a_modelo(fila, Inmueble)


async def marcar_posible_duplicado(inmueble_id: UUID, candidatos: list[UUID]) -> None:
    """Marca la bandera cross-portal (3A). No fusiona: solo señala."""
    await basedatos.ejecutar(
        "UPDATE inmuebles SET posible_duplicado_cross_portal = TRUE, "
        "inmuebles_duplicados_ids = $2 WHERE id = $1",
        inmueble_id, candidatos,
    )


async def registrar_precio(inmueble_id: UUID, precio: Decimal, moneda: str | None) -> None:
    await basedatos.ejecutar(
        "INSERT INTO historico_precios (inmueble_id, precio, moneda) VALUES ($1, $2, $3)",
        inmueble_id, precio, moneda,
    )


async def listar_historico_precios(inmueble_id: UUID) -> list[HistoricoPrecio]:
    filas = await basedatos.obtener_todos(
        "SELECT id, inmueble_id, precio, moneda, fecha_detectada "
        "FROM historico_precios WHERE inmueble_id = $1 ORDER BY fecha_detectada",
        inmueble_id,
    )
    return a_modelos(filas, HistoricoPrecio)


async def buscar_candidatos_duplicado(
    *, pais: str | None, ciudad: str | None, precio: Decimal | None,
    superficie: Decimal | None, excluir_portal: UUID, margen: Decimal = Decimal("0.05"),
) -> list[Inmueble]:
    """Candidatos a duplicado cross-portal (3A): misma zona, precio y superficie
    similares, en OTRO portal. No fusiona: solo localiza para marcar la bandera."""
    if precio is None or superficie is None or not ciudad:
        return []
    p_min, p_max = precio * (1 - margen), precio * (1 + margen)
    s_min, s_max = superficie * (1 - margen), superficie * (1 + margen)
    filas = await basedatos.obtener_todos(
        f"""
        SELECT {_COLUMNAS} FROM inmuebles
        WHERE portal_id <> $1 AND ciudad = $2
          AND ($3::char(2) IS NULL OR pais = $3)
          AND precio BETWEEN $4 AND $5
          AND COALESCE(superficie_util_m2, superficie_construida_m2) BETWEEN $6 AND $7
        LIMIT 10
        """,
        excluir_portal, ciudad, pais, p_min, p_max, s_min, s_max,
    )
    return a_modelos(filas, Inmueble)


async def contar_historico(inmueble_id: UUID) -> int:
    fila = await basedatos.obtener_uno(
        "SELECT count(*) AS n FROM historico_precios WHERE inmueble_id = $1", inmueble_id
    )
    return int(fila["n"]) if fila else 0


async def resumen_inventario(pais: str | None = None) -> dict:
    """Cuántos inmuebles hay y en qué estado de calidad.

    El ranking excluye NO_CALCULABLE y DESCARTADO_RIESGO, que es correcto pero deja
    inmuebles reales fuera de toda pantalla. Con esto el ranking puede decir
    "0 puntuados · 9 sin puntuar" en vez de un cero mudo.
    """
    condicion, args = "", []
    if pais:
        args.append(pais)
        condicion = " WHERE pais = $1"
    filas = await basedatos.obtener_todos(
        f"SELECT COALESCE(estado_calidad::text, 'SIN_ESTADO') AS estado, count(*) AS n "
        f"FROM inmuebles{condicion} GROUP BY 1",
        *args,
    )
    por_estado = {f["estado"]: f["n"] for f in filas}
    total = sum(por_estado.values())
    # "Puntuables" = los que el ranking puede llegar a mostrar.
    no_puntuables = por_estado.get("NO_CALCULABLE", 0) + por_estado.get("DESCARTADO_RIESGO", 0)
    return {
        "total": total,
        "por_estado": por_estado,
        "no_puntuables": no_puntuables,
    }
