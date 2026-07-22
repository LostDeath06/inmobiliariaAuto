"""Repositorio de configuración por país: mercado, umbrales, riesgos, tipos de
cambio y configuración global de la app."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from ..modelos.configuracion import (
    CatalogoRiesgo,
    ConfigMercadoPais,
    RiesgoPais,
    TipoCambio,
    UmbralPerfilPais,
)
from ..nucleo import basedatos
from .base import a_modelo, a_modelos

# --- config_app --------------------------------------------------------------


async def obtener_config_app(clave: str) -> str | None:
    fila = await basedatos.obtener_uno(
        "SELECT valor FROM config_app WHERE clave = $1", clave
    )
    return fila["valor"] if fila else None


async def establecer_config_app(clave: str, valor: str) -> None:
    await basedatos.ejecutar(
        "INSERT INTO config_app (clave, valor) VALUES ($1, $2) "
        "ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor",
        clave, valor,
    )


async def moneda_referencia() -> str:
    return (await obtener_config_app("moneda_referencia")) or "EUR"


# --- config_mercado_pais -----------------------------------------------------

_COL_MERCADO = """
    pais, monedas_nativas, tipo_interes_anual, tipo_interes_estado, ltv_max,
    ltv_max_estado, riesgo_pais, riesgo_pais_estado, sat_rentabilidad_neta,
    sat_rentabilidad_estado, sat_descuento_mercado, sat_descuento_estado, updated_at
"""


async def obtener_config_mercado(pais: str) -> ConfigMercadoPais | None:
    fila = await basedatos.obtener_uno(
        f"SELECT {_COL_MERCADO} FROM config_mercado_pais WHERE pais = $1", pais
    )
    return a_modelo(fila, ConfigMercadoPais)


async def listar_config_mercado() -> list[ConfigMercadoPais]:
    return a_modelos(
        await basedatos.obtener_todos(
            f"SELECT {_COL_MERCADO} FROM config_mercado_pais ORDER BY pais"
        ),
        ConfigMercadoPais,
    )


async def actualizar_config_mercado(pais: str, cambios: dict) -> ConfigMercadoPais | None:
    permitidas = {
        "monedas_nativas", "tipo_interes_anual", "tipo_interes_estado", "ltv_max",
        "ltv_max_estado", "riesgo_pais", "riesgo_pais_estado", "sat_rentabilidad_neta",
        "sat_rentabilidad_estado", "sat_descuento_mercado", "sat_descuento_estado",
    }
    campos = {k: v for k, v in cambios.items() if k in permitidas}
    if not campos:
        return await obtener_config_mercado(pais)
    asignaciones = ", ".join(f"{c} = ${i}" for i, c in enumerate(campos, start=2))
    fila = await basedatos.obtener_uno(
        f"UPDATE config_mercado_pais SET {asignaciones} WHERE pais = $1 "
        f"RETURNING {_COL_MERCADO}",
        pais, *campos.values(),
    )
    return a_modelo(fila, ConfigMercadoPais)


# --- umbrales_perfil_pais ----------------------------------------------------

_COL_UMBRAL = """
    perfil_id, pais, score_descarte, score_descarte_estado, roi_neto_minimo,
    roi_neto_minimo_estado, descuento_minimo_interes, descuento_minimo_estado, updated_at
"""


async def obtener_umbrales(perfil_id: UUID, pais: str) -> UmbralPerfilPais | None:
    fila = await basedatos.obtener_uno(
        f"SELECT {_COL_UMBRAL} FROM umbrales_perfil_pais WHERE perfil_id = $1 AND pais = $2",
        perfil_id, pais,
    )
    return a_modelo(fila, UmbralPerfilPais)


async def establecer_umbrales(perfil_id: UUID, pais: str, cambios: dict) -> UmbralPerfilPais | None:
    permitidas = {
        "score_descarte", "score_descarte_estado", "roi_neto_minimo",
        "roi_neto_minimo_estado", "descuento_minimo_interes", "descuento_minimo_estado",
    }
    campos = {k: v for k, v in cambios.items() if k in permitidas}
    if not campos:
        return await obtener_umbrales(perfil_id, pais)
    asignaciones = ", ".join(f"{c} = ${i}" for i, c in enumerate(campos, start=3))
    fila = await basedatos.obtener_uno(
        f"UPDATE umbrales_perfil_pais SET {asignaciones} "
        f"WHERE perfil_id = $1 AND pais = $2 RETURNING {_COL_UMBRAL}",
        perfil_id, pais, *campos.values(),
    )
    return a_modelo(fila, UmbralPerfilPais)


async def establecer_riesgo_pais(
    pais: str, codigo: str, es_eliminatorio: bool, penalizacion
) -> None:
    await basedatos.ejecutar(
        "INSERT INTO riesgos_pais (pais, codigo, es_eliminatorio, penalizacion) "
        "VALUES ($1,$2,$3,$4) "
        "ON CONFLICT (pais, codigo) DO UPDATE SET "
        "es_eliminatorio = EXCLUDED.es_eliminatorio, penalizacion = EXCLUDED.penalizacion",
        pais, codigo, es_eliminatorio, penalizacion,
    )


async def listar_umbrales(perfil_id: UUID | None = None) -> list[UmbralPerfilPais]:
    if perfil_id:
        filas = await basedatos.obtener_todos(
            f"SELECT {_COL_UMBRAL} FROM umbrales_perfil_pais WHERE perfil_id = $1 ORDER BY pais",
            perfil_id,
        )
    else:
        filas = await basedatos.obtener_todos(
            f"SELECT {_COL_UMBRAL} FROM umbrales_perfil_pais ORDER BY perfil_id, pais"
        )
    return a_modelos(filas, UmbralPerfilPais)


# --- tipos_cambio ------------------------------------------------------------


async def obtener_tasa(moneda_origen: str, moneda_destino: str) -> TipoCambio | None:
    """Tasa más reciente para el par. None si no hay ninguna (→ conversión PARCIAL)."""
    if moneda_origen == moneda_destino:
        return TipoCambio(
            moneda_origen=moneda_origen, moneda_destino=moneda_destino,
            tasa=Decimal(1), fuente="identidad", fecha=date.today(),
        )
    fila = await basedatos.obtener_uno(
        "SELECT moneda_origen, moneda_destino, tasa, fuente, fecha, updated_at "
        "FROM tipos_cambio WHERE moneda_origen = $1 AND moneda_destino = $2 "
        "ORDER BY fecha DESC LIMIT 1",
        moneda_origen, moneda_destino,
    )
    return a_modelo(fila, TipoCambio)


async def cargar_tasa(
    *, moneda_origen: str, moneda_destino: str, tasa: Decimal, fuente: str | None,
    fecha: date,
) -> None:
    await basedatos.ejecutar(
        "INSERT INTO tipos_cambio (moneda_origen, moneda_destino, tasa, fuente, fecha) "
        "VALUES ($1,$2,$3,$4,$5) "
        "ON CONFLICT (moneda_origen, moneda_destino, fecha) DO UPDATE SET "
        "tasa = EXCLUDED.tasa, fuente = EXCLUDED.fuente",
        moneda_origen, moneda_destino, tasa, fuente, fecha,
    )


# --- catálogo y riesgos por país ---------------------------------------------


async def listar_catalogo_riesgos() -> list[CatalogoRiesgo]:
    return a_modelos(
        await basedatos.obtener_todos(
            "SELECT codigo, clase, descripcion FROM catalogo_riesgos ORDER BY clase, codigo"
        ),
        CatalogoRiesgo,
    )


async def listar_riesgos_pais(pais: str) -> list[RiesgoPais]:
    return a_modelos(
        await basedatos.obtener_todos(
            "SELECT pais, codigo, es_eliminatorio, penalizacion, updated_at "
            "FROM riesgos_pais WHERE pais = $1",
            pais,
        ),
        RiesgoPais,
    )
