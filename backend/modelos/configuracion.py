"""Modelos de las tablas de configuración (donde vive el negocio, multi-país)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from .base import ModeloBase
from .enumeraciones import (
    ClaseSenal,
    EstadoParametro,
    NivelReforma,
    PerfilZona,
    TipoGastoAdquisicion,
)


class Pais(ModeloBase):
    codigo: str
    nombre: str


class ConfigApp(ModeloBase):
    clave: str
    valor: str | None = None


class PerfilInversor(ModeloBase):
    id: UUID
    nombre: str
    descripcion: str | None = None
    activo: bool = True
    es_predeterminado: bool = False
    pesos: dict = Field(default_factory=dict)
    supuestos: dict = Field(default_factory=dict)
    propietario_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ConfigMercadoPais(ModeloBase):
    pais: str
    monedas_nativas: list[str] = Field(default_factory=list)
    tipo_interes_anual: Decimal | None = None
    tipo_interes_estado: EstadoParametro = EstadoParametro.PROVISIONAL
    ltv_max: Decimal | None = None
    ltv_max_estado: EstadoParametro = EstadoParametro.PROVISIONAL
    riesgo_pais: Decimal = Decimal(0)
    riesgo_pais_estado: EstadoParametro = EstadoParametro.PROVISIONAL
    sat_rentabilidad_neta: Decimal | None = None
    sat_rentabilidad_estado: EstadoParametro = EstadoParametro.PROVISIONAL
    sat_descuento_mercado: Decimal | None = None
    sat_descuento_estado: EstadoParametro = EstadoParametro.PROVISIONAL
    updated_at: datetime | None = None


class UmbralPerfilPais(ModeloBase):
    perfil_id: UUID
    pais: str
    score_descarte: Decimal
    score_descarte_estado: EstadoParametro = EstadoParametro.VALIDADO
    roi_neto_minimo: Decimal | None = None
    roi_neto_minimo_estado: EstadoParametro = EstadoParametro.PROVISIONAL
    descuento_minimo_interes: Decimal | None = None
    descuento_minimo_estado: EstadoParametro = EstadoParametro.PROVISIONAL
    updated_at: datetime | None = None


class TipoCambio(ModeloBase):
    moneda_origen: str
    moneda_destino: str
    tasa: Decimal
    fuente: str | None = None
    fecha: date
    updated_at: datetime | None = None


class CatalogoRiesgo(ModeloBase):
    codigo: str
    clase: ClaseSenal
    descripcion: str | None = None


class RiesgoPais(ModeloBase):
    pais: str
    codigo: str
    es_eliminatorio: bool = False
    penalizacion: Decimal | None = None
    updated_at: datetime | None = None


class CosteReforma(ModeloBase):
    id: UUID
    pais: str
    nivel_reforma: NivelReforma
    coste_m2: Decimal | None = None  # NULL = dato ausente, nunca inventado
    moneda: str | None = None
    fuente: str | None = None
    updated_at: datetime | None = None


class GastoAdquisicion(ModeloBase):
    id: UUID
    pais: str
    region: str = ""
    concepto: str
    tipo: TipoGastoAdquisicion
    valor: Decimal | None = None
    moneda: str | None = None
    fuente: str | None = None
    updated_at: datetime | None = None


class BenchmarkZona(ModeloBase):
    id: UUID
    pais: str
    ciudad: str
    barrio: str | None = None
    moneda: str | None = None
    precio_m2_venta_medio: Decimal | None = None
    precio_m2_alquiler_medio: Decimal | None = None  # larga estancia (€/m²/mes)
    rentabilidad_bruta_media_zona: Decimal | None = None
    # Perfil de la zona y datos de CORTA estancia (turístico). Los carga el propietario;
    # NULL = ausente. El motor de cashflow no los usa todavía (ver 0007).
    perfil_zona: PerfilZona = PerfilZona.ESTANDAR
    adr_medio: Decimal | None = None                 # tarifa media por noche
    ocupacion_media: Decimal | None = None           # 0..1
    gastos_gestion_corta_pct: Decimal | None = None
    fuente: str | None = None
    fecha_dato: date | None = None
    updated_at: datetime | None = None


class Portal(ModeloBase):
    id: UUID
    nombre: str
    url_raiz: str
    pais: str | None = None
    activo: bool = True
    notas_extraccion: str | None = None
    tasa_exito_historica: Decimal | None = None
    propietario_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
