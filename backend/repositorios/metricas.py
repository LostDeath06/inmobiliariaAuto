"""Repositorio de métricas financieras."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from ..modelos.enumeraciones import CalidadDato
from ..modelos.metricas import MetricasFinancieras
from ..nucleo import basedatos
from .base import a_modelo

_COLUMNAS = """
    id, inmueble_id, version_motor, moneda, moneda_referencia, tasa_cambio_usada,
    conversion_parcial, snapshot_supuestos, snapshot_mercado_pais, snapshot_gastos,
    snapshot_coste_reforma, metricas, metricas_referencia, inputs_auditoria,
    estado_calidad, campos_faltantes, created_at, updated_at
"""


async def obtener(inmueble_id: UUID) -> MetricasFinancieras | None:
    fila = await basedatos.obtener_uno(
        f"SELECT {_COLUMNAS} FROM metricas_financieras WHERE inmueble_id = $1", inmueble_id
    )
    return a_modelo(fila, MetricasFinancieras)


async def guardar(
    *,
    inmueble_id: UUID,
    version_motor: str,
    moneda: str | None,
    moneda_referencia: str | None,
    tasa_cambio_usada: Decimal | None,
    conversion_parcial: bool,
    snapshot_supuestos: dict,
    snapshot_mercado_pais: dict | None,
    snapshot_gastos: dict | None,
    snapshot_coste_reforma: dict | None,
    metricas: dict,
    metricas_referencia: dict | None,
    inputs_auditoria: dict,
    estado_calidad: CalidadDato,
    campos_faltantes: list[str],
) -> MetricasFinancieras:
    fila = await basedatos.obtener_uno(
        f"""
        INSERT INTO metricas_financieras
            (inmueble_id, version_motor, moneda, moneda_referencia, tasa_cambio_usada,
             conversion_parcial, snapshot_supuestos, snapshot_mercado_pais,
             snapshot_gastos, snapshot_coste_reforma, metricas, metricas_referencia,
             inputs_auditoria, estado_calidad, campos_faltantes)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)
        ON CONFLICT (inmueble_id) DO UPDATE SET
            version_motor = EXCLUDED.version_motor,
            moneda = EXCLUDED.moneda,
            moneda_referencia = EXCLUDED.moneda_referencia,
            tasa_cambio_usada = EXCLUDED.tasa_cambio_usada,
            conversion_parcial = EXCLUDED.conversion_parcial,
            snapshot_supuestos = EXCLUDED.snapshot_supuestos,
            snapshot_mercado_pais = EXCLUDED.snapshot_mercado_pais,
            snapshot_gastos = EXCLUDED.snapshot_gastos,
            snapshot_coste_reforma = EXCLUDED.snapshot_coste_reforma,
            metricas = EXCLUDED.metricas,
            metricas_referencia = EXCLUDED.metricas_referencia,
            inputs_auditoria = EXCLUDED.inputs_auditoria,
            estado_calidad = EXCLUDED.estado_calidad,
            campos_faltantes = EXCLUDED.campos_faltantes
        RETURNING {_COLUMNAS}
        """,
        inmueble_id, version_motor, moneda, moneda_referencia, tasa_cambio_usada,
        conversion_parcial, snapshot_supuestos, snapshot_mercado_pais, snapshot_gastos,
        snapshot_coste_reforma, metricas, metricas_referencia, inputs_auditoria,
        estado_calidad.value, campos_faltantes,
    )
    return a_modelo(fila, MetricasFinancieras)  # type: ignore[return-value]
