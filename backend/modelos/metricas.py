"""Modelo de `metricas_financieras` (salida del motor determinista)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from .base import ModeloBase
from .enumeraciones import CalidadDato


class MetricasFinancieras(ModeloBase):
    id: UUID
    inmueble_id: UUID
    version_motor: str
    moneda: str | None = None            # moneda nativa de las métricas
    moneda_referencia: str | None = None
    tasa_cambio_usada: Decimal | None = None
    conversion_parcial: bool = False     # sin tasa disponible → PARCIAL
    snapshot_supuestos: dict
    snapshot_mercado_pais: dict | None = None
    snapshot_gastos: dict | None = None
    snapshot_coste_reforma: dict | None = None
    metricas: dict = Field(default_factory=dict)             # en moneda nativa
    metricas_referencia: dict | None = None                 # convertidas
    inputs_auditoria: dict = Field(default_factory=dict)     # fórmula + inputs (hover UI)
    estado_calidad: CalidadDato
    campos_faltantes: list[str] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None
