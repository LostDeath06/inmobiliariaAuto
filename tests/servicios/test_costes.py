"""Tarifación de tokens: la aritmética del gasto.

Lo que protege:
1. Las CUATRO clases de token se tarifan con su precio propio. Contar solo
   entrada/salida es lo que hacía invisible el gasto real de un agente, donde la
   escritura de caché domina.
2. Los precios salen de BD, no de Python (Principio 2).
3. Sin precio configurado el coste es 0 CON AVISO, nunca un número inventado.
"""

from decimal import Decimal

import pytest

from backend.modelos.costes import PrecioModelo
from backend.servicios import costes

D = Decimal

# Sonnet 5 a precio introductorio (vigente 2026-07-24).
_SONNET_5 = PrecioModelo(
    modelo="claude-sonnet-5",
    usd_entrada_por_m=D("2"), usd_salida_por_m=D("10"),
    usd_cache_write_por_m=D("2.50"), usd_cache_read_por_m=D("0.20"),
)


@pytest.fixture
def con_precio(monkeypatch):
    async def falso(modelo):
        return _SONNET_5 if modelo == "claude-sonnet-5" else None
    monkeypatch.setattr(costes.repo, "obtener_precio", falso)


@pytest.mark.asyncio
async def test_tarifa_las_cuatro_clases_de_token(con_precio):
    """1000 de cada clase: 0.002 + 0.010 + 0.0025 + 0.0002 = 0.0147 USD."""
    coste, aviso = await costes.calcular_coste(
        "claude-sonnet-5", entrada=1000, salida=1000, cache_write=1000, cache_read=1000,
    )
    assert aviso is None
    assert coste == D("0.0147")


@pytest.mark.asyncio
async def test_el_reprocesado_real_de_9_inmuebles(con_precio):
    """Cifras reales medidas: 30.538 entrada + 7.997 salida, sin caché.

    30538/1e6*2 = 0.061076 · 7997/1e6*10 = 0.07997 → 0.141046 USD.
    Los $3/$15 hardcodeados que había antes daban 0.2116: un 50% de más.
    """
    coste, _ = await costes.calcular_coste("claude-sonnet-5", entrada=30538, salida=7997)
    assert coste == D("0.141046")
    assert coste < D("0.15")  # céntimos: el analista NO es el problema


@pytest.mark.asyncio
async def test_la_escritura_de_cache_domina_el_gasto_de_un_agente(con_precio):
    """La sonda trivial de OpenClaw: 19.254 tokens de cacheWrite.

    19254/1e6*2.50 = 0.048135 USD por una pregunta trivial — más caro que
    analizar tres inmuebles enteros. Es el hallazgo que motivó todo esto.
    """
    sonda, _ = await costes.calcular_coste(
        "claude-sonnet-5", entrada=300, salida=150, cache_write=19254, cache_read=0,
    )
    inmueble, _ = await costes.calcular_coste(
        "claude-sonnet-5", entrada=3393, salida=889,
    )
    assert sonda > inmueble * 3


@pytest.mark.asyncio
async def test_leer_de_cache_es_12_veces_mas_barato_que_escribirla(con_precio):
    """0.20 vs 2.50 por millón. Reutilizar la sesión es lo que lo convierte en ahorro."""
    escribir, _ = await costes.calcular_coste("claude-sonnet-5", cache_write=1_000_000)
    leer, _ = await costes.calcular_coste("claude-sonnet-5", cache_read=1_000_000)
    assert escribir == D("2.50")
    assert leer == D("0.20")
    assert escribir / leer == D("12.5")


@pytest.mark.asyncio
async def test_sin_precio_configurado_coste_cero_con_aviso(con_precio):
    """Nunca un número inventado: 0 explícito y un aviso que nombra el modelo."""
    coste, aviso = await costes.calcular_coste("modelo-que-no-existe", entrada=10_000)
    assert coste == D(0)
    assert aviso is not None and "modelo-que-no-existe" in aviso


@pytest.mark.asyncio
async def test_sin_modelo_no_se_tarifa(con_precio):
    coste, aviso = await costes.calcular_coste(None, entrada=10_000)
    assert coste == D(0)
    assert aviso is not None
