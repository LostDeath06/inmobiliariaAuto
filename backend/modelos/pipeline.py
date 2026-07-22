"""Modelos de las tablas del pipeline (multi-divisa)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field

from .base import ModeloBase
from .enumeraciones import CalidadDato, EstadoJob, TipoAnunciante


class Busqueda(ModeloBase):
    id: UUID
    portal_id: UUID
    ciudad: str | None = None
    presupuesto_min: Decimal | None = None
    presupuesto_max: Decimal | None = None
    moneda: str | None = None
    tipo_inmueble: str | None = None
    filtros_extra: dict = Field(default_factory=dict)
    activa: bool = True
    frecuencia_cron: str | None = None
    ultima_ejecucion: datetime | None = None
    proxima_ejecucion: datetime | None = None
    propietario_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class Job(ModeloBase):
    id: UUID
    busqueda_id: UUID
    estado: EstadoJob = EstadoJob.PENDIENTE
    prompt_enviado: str | None = None
    openclaw_job_id: str | None = None
    intentos: int = 0
    error_mensaje: str | None = None
    tokens_entrada: int | None = None
    tokens_salida: int | None = None
    coste_estimado_usd: Decimal | None = None
    total_resultados_detectados: int | None = None
    total_anuncios_extraidos: int | None = None
    total_anuncios_validos: int | None = None
    total_anuncios_cuarentena: int | None = None
    extraccion_completa: bool | None = None
    iniciado_en: datetime | None = None
    finalizado_en: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AnuncioCrudoRegistro(ModeloBase):
    """Fila de `anuncios_crudos`. Inmutable, append-only."""

    id: UUID
    job_id: UUID
    url_anuncio: str
    payload_json: dict
    hash_contenido: str
    created_at: datetime | None = None


class AnuncioCuarentena(ModeloBase):
    """Fila de `anuncios_cuarentena` (2A)."""

    id: UUID
    job_id: UUID
    url_anuncio: str | None = None
    payload_crudo: dict
    errores_validacion: list[dict] = Field(default_factory=list)
    created_at: datetime | None = None


class Inmueble(ModeloBase):
    id: UUID
    portal_id: UUID
    id_portal: str | None = None
    url_anuncio: str
    hash_deduplicacion: str
    titulo: str | None = None
    precio: Decimal | None = None
    moneda: str | None = None  # ISO 4217 nativa del anuncio
    superficie_construida_m2: Decimal | None = None
    superficie_util_m2: Decimal | None = None
    habitaciones: int | None = None
    banos: int | None = None
    planta: str | None = None
    tiene_ascensor: bool | None = None
    ano_construccion: int | None = None
    certificado_energetico: str | None = None
    direccion_texto: str | None = None
    barrio: str | None = None
    ciudad: str | None = None
    provincia: str | None = None
    pais: str | None = None
    codigo_postal: str | None = None
    latitud: Decimal | None = None
    longitud: Decimal | None = None
    descripcion_completa: str | None = None
    caracteristicas_listadas: list[str] = Field(default_factory=list)
    urls_imagenes: list[str] = Field(default_factory=list)
    tipo_anunciante: TipoAnunciante | None = None
    fecha_publicacion: datetime | None = None
    gastos_comunidad_mes: Decimal | None = None
    estado_calidad: CalidadDato | None = None
    posible_duplicado_cross_portal: bool = False  # 3A
    inmuebles_duplicados_ids: list[UUID] = Field(default_factory=list)
    primer_visto: datetime | None = None
    ultimo_visto: datetime | None = None
    propietario_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class HistoricoPrecio(ModeloBase):
    id: UUID
    inmueble_id: UUID
    precio: Decimal
    moneda: str | None = None
    fecha_detectada: datetime
