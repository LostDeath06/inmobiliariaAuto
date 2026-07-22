"""Salida del analista cualitativo (Claude). §8.2.

SOLO juicio cualitativo estructurado: enums, booleanos, categorías y texto corto.
CERO números calculados. `extra="forbid"` rechaza cualquier campo inesperado; el
test anti-números (Fase 6) verifica que ningún campo numérico calculado aparezca
aquí (protege el Principio 1).

`senales_riesgo` y `senales_oportunidad` son códigos de texto del catálogo por país
(no enum rígido): se validan contra el catálogo del país en el servicio analista
(`validar_senales`). Los códigos fuera de catálogo NO se pierden en silencio: se
separan a `senales_no_reconocidas` (campo calculado por el sistema, no emitido por
Claude) para que sean visibles.
"""

from __future__ import annotations

from pydantic import Field, field_validator

from .base import ModeloBase
from .enumeraciones import (
    AptoTernario,
    CalidadDescripcion,
    CoherenciaPrecio,
    EstadoConservacion,
    NivelConfianza,
    NivelReforma,
    Tipologia,
)


_MAX_RESUMEN = 1000


class AnalisisCualitativo(ModeloBase):
    """Juicio cualitativo de Claude sobre un inmueble. §8.2."""

    estado_conservacion: EstadoConservacion
    nivel_reforma_estimado: NivelReforma
    tipologia: Tipologia
    senales_riesgo: list[str] = Field(default_factory=list)
    senales_oportunidad: list[str] = Field(default_factory=list)
    # Códigos que Claude devolvió pero el catálogo del país NO contempla. Lo calcula
    # el sistema al validar la salida (nunca lo emite Claude → se excluye del esquema
    # que se le entrega). Visible en la ficha y el monitor: un código aquí significa o
    # bien que Claude alucina, o bien que falta un código en el catálogo de ese país.
    senales_no_reconocidas: list[str] = Field(default_factory=list)
    apto_alquiler_larga_estancia: AptoTernario
    apto_alquiler_turistico: AptoTernario
    potencial_division_horizontal: AptoTernario
    calidad_descripcion: CalidadDescripcion
    coherencia_precio_descripcion: CoherenciaPrecio
    # Resumen corto en texto libre. El límite es holgado (un resumen, no un ensayo) y,
    # si el modelo se pasa, se recorta en vez de tumbar TODO el análisis: fallar el
    # análisis entero por un resumen largo seria un mal modo de fallo. Es texto, no una
    # cifra: no roza el Principio 1.
    resumen_analista: str = Field(max_length=_MAX_RESUMEN)
    banderas_rojas_texto: list[str] = Field(default_factory=list)
    nivel_confianza: NivelConfianza
    campos_no_inferibles: list[str] = Field(default_factory=list)

    @field_validator("resumen_analista", mode="before")
    @classmethod
    def _recortar_resumen(cls, valor):
        if isinstance(valor, str) and len(valor) > _MAX_RESUMEN:
            return valor[:_MAX_RESUMEN].rstrip()
        return valor
