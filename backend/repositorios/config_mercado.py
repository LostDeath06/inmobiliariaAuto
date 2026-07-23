"""Repositorio de configuración de mercado: costes de reforma, gastos de
adquisición y benchmarks de zona.

Estas tablas pueden estar vacías o con NULL (dato ausente): el repositorio NUNCA
los rellena; los devuelve tal cual para que la UI marque los huecos y el motor
financiero decida NO_CALCULABLE.
"""

from __future__ import annotations

from decimal import Decimal

from ..modelos.configuracion import BenchmarkZona, CosteReforma, GastoAdquisicion
from ..modelos.enumeraciones import NivelReforma
from ..nucleo import basedatos
from .base import a_modelo, a_modelos

_COL_COSTE = "id, pais, nivel_reforma, coste_m2, moneda, fuente, updated_at"


async def listar_costes_reforma(pais: str | None = None) -> list[CosteReforma]:
    if pais:
        filas = await basedatos.obtener_todos(
            f"SELECT {_COL_COSTE} FROM costes_reforma WHERE pais = $1 ORDER BY nivel_reforma",
            pais,
        )
    else:
        filas = await basedatos.obtener_todos(
            f"SELECT {_COL_COSTE} FROM costes_reforma ORDER BY pais, nivel_reforma"
        )
    return a_modelos(filas, CosteReforma)


async def obtener_coste_reforma(pais: str, nivel: NivelReforma) -> CosteReforma | None:
    fila = await basedatos.obtener_uno(
        f"SELECT {_COL_COSTE} FROM costes_reforma WHERE pais = $1 AND nivel_reforma = $2",
        pais, nivel.value,
    )
    return a_modelo(fila, CosteReforma)


async def establecer_coste_reforma(
    pais: str, nivel: NivelReforma, coste_m2: Decimal | None, moneda: str | None,
    fuente: str | None,
) -> CosteReforma:
    fila = await basedatos.obtener_uno(
        f"""
        INSERT INTO costes_reforma (pais, nivel_reforma, coste_m2, moneda, fuente)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (pais, nivel_reforma) DO UPDATE SET
            coste_m2 = EXCLUDED.coste_m2, moneda = EXCLUDED.moneda, fuente = EXCLUDED.fuente
        RETURNING {_COL_COSTE}
        """,
        pais, nivel.value, coste_m2, moneda, fuente,
    )
    return a_modelo(fila, CosteReforma)  # type: ignore[return-value]


_COL_GASTO = (
    "id, pais, region, concepto, tipo, valor, moneda, exento_confotur, fuente, updated_at"
)


async def listar_gastos_adquisicion(
    pais: str | None = None, region: str | None = None
) -> list[GastoAdquisicion]:
    condiciones, args = [], []
    if pais:
        args.append(pais)
        condiciones.append(f"pais = ${len(args)}")
    if region is not None:
        args.append(region)
        condiciones.append(f"region = ${len(args)}")
    where = f" WHERE {' AND '.join(condiciones)}" if condiciones else ""
    filas = await basedatos.obtener_todos(
        f"SELECT {_COL_GASTO} FROM gastos_adquisicion{where} ORDER BY pais, region, concepto",
        *args,
    )
    return a_modelos(filas, GastoAdquisicion)


_COL_BENCH = """
    id, pais, ciudad, barrio, moneda, precio_m2_venta_medio, precio_m2_alquiler_medio,
    rentabilidad_bruta_media_zona, perfil_zona, adr_medio, ocupacion_media,
    gastos_gestion_corta_pct, fuente, fecha_dato, updated_at
"""


async def obtener_benchmark_zona(
    pais: str, ciudad: str, barrio: str | None = None
) -> BenchmarkZona | None:
    """Devuelve el benchmark más específico disponible (barrio → ciudad)."""
    if barrio:
        fila = await basedatos.obtener_uno(
            f"SELECT {_COL_BENCH} FROM benchmarks_zona "
            f"WHERE pais = $1 AND ciudad = $2 AND barrio = $3",
            pais, ciudad, barrio,
        )
        if fila is not None:
            return a_modelo(fila, BenchmarkZona)
    fila = await basedatos.obtener_uno(
        f"SELECT {_COL_BENCH} FROM benchmarks_zona "
        f"WHERE pais = $1 AND ciudad = $2 AND barrio IS NULL",
        pais, ciudad,
    )
    return a_modelo(fila, BenchmarkZona)


async def establecer_gasto_adquisicion(
    *, pais: str, region: str, concepto: str, tipo: str, valor: Decimal | None,
    moneda: str | None, fuente: str | None, exento_confotur: bool = False,
) -> GastoAdquisicion:
    fila = await basedatos.obtener_uno(
        f"""
        INSERT INTO gastos_adquisicion
            (pais, region, concepto, tipo, valor, moneda, fuente, exento_confotur)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        ON CONFLICT (pais, region, concepto) DO UPDATE SET
            tipo = EXCLUDED.tipo, valor = EXCLUDED.valor, moneda = EXCLUDED.moneda,
            fuente = EXCLUDED.fuente, exento_confotur = EXCLUDED.exento_confotur
        RETURNING {_COL_GASTO}
        """,
        pais, region, concepto, tipo, valor, moneda, fuente, exento_confotur,
    )
    return a_modelo(fila, GastoAdquisicion)  # type: ignore[return-value]


async def establecer_benchmark(
    *, pais: str, ciudad: str, barrio: str | None, moneda: str | None,
    precio_m2_venta_medio: Decimal | None, precio_m2_alquiler_medio: Decimal | None,
    rentabilidad_bruta_media_zona: Decimal | None, fuente: str | None, fecha_dato,
    perfil_zona: str | None = None, adr_medio: Decimal | None = None,
    ocupacion_media: Decimal | None = None, gastos_gestion_corta_pct: Decimal | None = None,
) -> BenchmarkZona:
    """Alta/actualización de benchmark de zona.

    Los campos de corta estancia (`adr_medio`, `ocupacion_media`, …) y `perfil_zona`
    solo se sobrescriben si se pasan (COALESCE): así actualizar el alquiler de larga
    no borra la marca turística ya cargada, y viceversa.
    """
    fila = await basedatos.obtener_uno(
        f"""
        INSERT INTO benchmarks_zona
            (pais, ciudad, barrio, moneda, precio_m2_venta_medio, precio_m2_alquiler_medio,
             rentabilidad_bruta_media_zona, perfil_zona, adr_medio, ocupacion_media,
             gastos_gestion_corta_pct, fuente, fecha_dato)
        VALUES ($1,$2,$3,$4,$5,$6,$7,COALESCE($8,'ESTANDAR')::perfil_zona,$9,$10,$11,$12,$13)
        ON CONFLICT (pais, ciudad, COALESCE(barrio, '')) DO UPDATE SET
            moneda = EXCLUDED.moneda,
            precio_m2_venta_medio = EXCLUDED.precio_m2_venta_medio,
            precio_m2_alquiler_medio = EXCLUDED.precio_m2_alquiler_medio,
            rentabilidad_bruta_media_zona = EXCLUDED.rentabilidad_bruta_media_zona,
            perfil_zona = COALESCE($8::perfil_zona, benchmarks_zona.perfil_zona),
            adr_medio = COALESCE($9, benchmarks_zona.adr_medio),
            ocupacion_media = COALESCE($10, benchmarks_zona.ocupacion_media),
            gastos_gestion_corta_pct = COALESCE($11, benchmarks_zona.gastos_gestion_corta_pct),
            fuente = EXCLUDED.fuente, fecha_dato = EXCLUDED.fecha_dato
        RETURNING {_COL_BENCH}
        """,
        pais, ciudad, barrio, moneda, precio_m2_venta_medio, precio_m2_alquiler_medio,
        rentabilidad_bruta_media_zona, perfil_zona, adr_medio, ocupacion_media,
        gastos_gestion_corta_pct, fuente, fecha_dato,
    )
    return a_modelo(fila, BenchmarkZona)  # type: ignore[return-value]


async def listar_benchmarks_zona(pais: str | None = None) -> list[BenchmarkZona]:
    if pais:
        filas = await basedatos.obtener_todos(
            f"SELECT {_COL_BENCH} FROM benchmarks_zona WHERE pais = $1 ORDER BY ciudad, barrio",
            pais,
        )
    else:
        filas = await basedatos.obtener_todos(
            f"SELECT {_COL_BENCH} FROM benchmarks_zona ORDER BY pais, ciudad, barrio"
        )
    return a_modelos(filas, BenchmarkZona)


# --- Regiones fiscales -------------------------------------------------------
# El ITP español varía por comunidad autónoma, así que `gastos_adquisicion` tiene
# una fila por comunidad. Pero el inmueble solo trae `provincia`: sin este mapa,
# el servicio no sabría qué fila le toca y acabaría sumando todas.


async def resolver_region(pais: str, provincia: str | None) -> str | None:
    """Región fiscal de una provincia. None si no hay mapeo (no se adivina)."""
    if not provincia:
        return None
    fila = await basedatos.obtener_uno(
        "SELECT region FROM regiones_fiscales WHERE pais = $1 AND lower(provincia) = lower($2)",
        pais, provincia,
    )
    return fila["region"] if fila else None


async def establecer_region_fiscal(
    *, pais: str, provincia: str, region: str, fuente: str | None = None
) -> None:
    await basedatos.ejecutar(
        """
        INSERT INTO regiones_fiscales (pais, provincia, region, fuente)
        VALUES ($1,$2,$3,$4)
        ON CONFLICT (pais, provincia) DO UPDATE SET
            region = EXCLUDED.region, fuente = EXCLUDED.fuente
        """,
        pais, provincia, region, fuente,
    )


async def listar_regiones_fiscales(pais: str | None = None) -> list[dict]:
    if pais:
        filas = await basedatos.obtener_todos(
            "SELECT pais, provincia, region, fuente FROM regiones_fiscales "
            "WHERE pais = $1 ORDER BY provincia",
            pais,
        )
    else:
        filas = await basedatos.obtener_todos(
            "SELECT pais, provincia, region, fuente FROM regiones_fiscales "
            "ORDER BY pais, provincia"
        )
    return [dict(f) for f in filas]


async def borrar_regiones_fiscales(pais: str) -> int:
    return await basedatos.ejecutar(
        "DELETE FROM regiones_fiscales WHERE pais = $1", pais
    )


async def borrar_gastos_adquisicion(pais: str, fuente_like: str | None = None) -> int:
    """Purga usada por el script de carga (--purgar).

    El filtro por fuente va en `lower(...) LIKE`: purgar por texto exacto ya nos
    mordió una vez (un benchmark 'demo' en minúscula sobrevivió a la limpieza y
    contaminó un score real).
    """
    if fuente_like:
        return await basedatos.ejecutar(
            "DELETE FROM gastos_adquisicion WHERE pais = $1 AND lower(fuente) LIKE lower($2)",
            pais, fuente_like,
        )
    return await basedatos.ejecutar("DELETE FROM gastos_adquisicion WHERE pais = $1", pais)
