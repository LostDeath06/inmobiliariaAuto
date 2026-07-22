"""Conversión de divisa. La hace Python con la tasa de BD, nunca Claude, nunca
hardcodeada. Sin tasa disponible → conversión PARCIAL (jamás una tasa inventada).
"""

from __future__ import annotations

from decimal import Decimal

from ..repositorios import configuracion_pais


class ResultadoConversion:
    def __init__(self, valor: Decimal | None, tasa: Decimal | None, parcial: bool):
        self.valor = valor
        self.tasa = tasa
        self.parcial = parcial  # True si no había tasa (dato ausente)


async def convertir(
    monto: Decimal | None, moneda_origen: str | None, moneda_destino: str | None
) -> ResultadoConversion:
    if monto is None or moneda_origen is None or moneda_destino is None:
        return ResultadoConversion(None, None, True)
    tc = await configuracion_pais.obtener_tasa(moneda_origen, moneda_destino)
    if tc is None:
        # Sin tasa: no se inventa. La conversión queda pendiente (PARCIAL).
        return ResultadoConversion(None, None, True)
    return ResultadoConversion(monto * tc.tasa, tc.tasa, False)


async def convertir_dict(
    metricas: dict[str, Decimal], moneda_origen: str | None, moneda_destino: str | None
) -> tuple[dict | None, Decimal | None, bool]:
    """Convierte todas las cifras de un dict de métricas (las ratios no se tocan).

    Devuelve (metricas_convertidas | None, tasa | None, parcial).
    """
    if not metricas or moneda_origen is None or moneda_destino is None:
        return None, None, True
    if moneda_origen == moneda_destino:
        return {k: str(v) for k, v in metricas.items()}, Decimal(1), False
    tc = await configuracion_pais.obtener_tasa(moneda_origen, moneda_destino)
    if tc is None:
        return None, None, True
    # Solo se convierten importes monetarios; ratios (roi, cap, descuento) no.
    ratios = {"roi_neto", "cap_rate", "rentabilidad_bruta", "descuento_mercado"}
    convertidas = {}
    for clave, valor in metricas.items():
        convertidas[clave] = str(valor if clave in ratios else valor * tc.tasa)
    return convertidas, tc.tasa, False
