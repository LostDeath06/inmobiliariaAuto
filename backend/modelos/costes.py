"""Modelos de contabilidad de tokens y coste.

El coste NO es criterio de inversión: es gasto operativo. Vive aquí separado del
dominio financiero (motor_financiero) para que nadie los confunda.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import Field

from .base import ModeloBase


class FuenteUso(str, Enum):
    """Quién gastó. Son las dos únicas cosas que llaman a la API."""

    ANALISTA = "ANALISTA"   # backend → juicio cualitativo
    OPENCLAW = "OPENCLAW"   # agente de extracción, vía adaptador


class PrecioModelo(ModeloBase):
    """USD por millón de tokens, por clase de token.

    Cuatro precios, no uno: la escritura de caché cuesta 1.25x la entrada y la
    lectura 0.1x. Ignorar esa distinción es lo que hacía invisible el gasto real.
    """

    modelo: str
    usd_entrada_por_m: Decimal
    usd_salida_por_m: Decimal
    usd_cache_write_por_m: Decimal
    usd_cache_read_por_m: Decimal
    fuente: str | None = None
    updated_at: datetime | None = None


class UsoTokens(ModeloBase):
    """Una llamada facturable. Grano de evento: las vistas se agregan encima."""

    id: UUID | None = None
    fuente: FuenteUso
    modelo: str | None = None
    job_id: UUID | None = None
    inmueble_id: UUID | None = None
    tokens_entrada: int = 0
    tokens_salida: int = 0
    tokens_cache_write: int = 0
    tokens_cache_read: int = 0
    coste_usd: Decimal = Decimal(0)
    detalle: dict = Field(default_factory=dict)
    created_at: datetime | None = None
