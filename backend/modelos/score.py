"""Modelo de `scores`. Clave compuesta (inmueble_id, perfil_id)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from .base import ModeloBase
from .enumeraciones import CalidadDato


class Score(ModeloBase):
    inmueble_id: UUID
    perfil_id: UUID
    # score_bruto = antes del riesgo país (salvaguarda del toggle "sin riesgo país").
    score_bruto: Decimal | None = None
    # score_total = score_bruto * (1 - riesgo_pais).
    score_total: Decimal | None = None
    riesgo_pais_aplicado: Decimal | None = None
    # Contribución exacta de cada componente: el usuario debe ver POR QUÉ sacó 87.
    desglose: dict = Field(default_factory=dict)
    estado_calidad: CalidadDato
    motivo_descarte: list[str] = Field(default_factory=list)   # riesgos eliminatorios
    usa_parametros_provisionales: bool = False
    obsoleto: bool = False
    version_pesos: str | None = None
    calculado_en: datetime | None = None
