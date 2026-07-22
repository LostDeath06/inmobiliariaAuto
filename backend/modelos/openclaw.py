"""Contrato de salida de OpenClaw (§5.4, multi-divisa).

El prompt que se le envía a OpenClaw es libre; la salida NO. `extra="forbid"`.

Regla de oro de la ingesta:
- Campo ausente → `null` explícito.
- Campo no leído → `null` explícito.
- JAMÁS un valor inventado, estimado o "plausible".

El precio va como `precio` + `moneda` (ISO 4217): el sistema es multi-país
(ES/DO/VE) desde el día uno y opera en la moneda nativa del anuncio.

Estrategia de validación (2A): el sobre se valida entero; la lista `anuncios` se
recibe como crudo (list[dict]) y cada anuncio se valida por separado en la ingesta,
para poner en cuarentena los inválidos sin tumbar el lote.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .base import ModeloBase
from .enumeraciones import TipoAnunciante


class AnuncioOpenClaw(ModeloBase):
    """Un anuncio individual extraído por OpenClaw. Ver §5.4."""

    url_anuncio: str  # obligatorio, único
    id_portal: str | None = None
    titulo: str | None = None
    precio: float | None = None
    moneda: str | None = None  # ISO 4217 (EUR, USD, DOP, ...)
    superficie_construida_m2: float | None = None
    superficie_util_m2: float | None = None
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
    latitud: float | None = None
    longitud: float | None = None
    descripcion_completa: str | None = None
    caracteristicas_listadas: list[str] = Field(default_factory=list)
    urls_imagenes: list[str] = Field(default_factory=list)
    tipo_anunciante: TipoAnunciante | None = None
    fecha_publicacion: str | None = None  # ISO-8601
    gastos_comunidad_mes: float | None = None
    campos_no_encontrados: list[str] = Field(default_factory=list)
    notas_extraccion: str | None = None


class BusquedaEjecutada(ModeloBase):
    """Resumen de la búsqueda que OpenClaw ejecutó. Ver §5.4."""

    ciudad: str | None = None
    presupuesto_min: float | None = None
    presupuesto_max: float | None = None
    moneda: str | None = None
    tipo_inmueble: str | None = None
    filtros_aplicados: list[str] = Field(default_factory=list)
    url_resultados: str | None = None


class SobreScraping(ModeloBase):
    """Sobre completo devuelto por OpenClaw. Ver §5.4.

    `anuncios` se recibe como crudo para validación por anuncio (2A).
    """

    job_id: str  # uuid, obligatorio
    portal_url: str  # obligatorio
    portal_nombre: str | None = None
    fecha_extraccion_utc: str  # ISO-8601, obligatorio
    busqueda_ejecutada: BusquedaEjecutada | None = None
    total_resultados_detectados: int | None = None
    total_anuncios_extraidos: int  # obligatorio
    anuncios: list[dict[str, Any]] = Field(default_factory=list)
    errores_navegacion: list[str] = Field(default_factory=list)
    advertencias: list[str] = Field(default_factory=list)
    extraccion_completa: bool  # obligatorio
