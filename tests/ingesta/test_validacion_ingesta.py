"""Tests de validación de la ingesta (§12.3, §12.4).

Un JSON de OpenClaw malformado DEBE ser rechazado. Un campo ausente DEBE quedar
`null`, nunca inventado.
"""

import pytest
from pydantic import ValidationError

from backend.modelos.openclaw import AnuncioOpenClaw, SobreScraping
from backend.servicios import constructor_prompt


def test_anuncio_valido_se_acepta():
    a = AnuncioOpenClaw(url_anuncio="https://portal/1", precio=150000, moneda="EUR")
    assert a.precio == 150000
    assert a.moneda == "EUR"


def test_anuncio_sin_url_se_rechaza():
    with pytest.raises(ValidationError):
        AnuncioOpenClaw(precio=100000, moneda="USD")


def test_anuncio_con_campo_desconocido_se_rechaza():
    # extra="forbid": un campo no declarado es un error (no se traga en silencio).
    with pytest.raises(ValidationError):
        AnuncioOpenClaw(url_anuncio="u", rentabilidad_calculada=8.5)


def test_sobre_sin_campo_obligatorio_se_rechaza():
    with pytest.raises(ValidationError):
        SobreScraping(
            job_id="j", portal_url="https://p", fecha_extraccion_utc="2026-07-14T00:00:00Z",
            extraccion_completa=True,  # falta total_anuncios_extraidos
        )


def test_no_invencion_campo_ausente_queda_null():
    # precio y moneda ausentes → None explícito, NUNCA un valor plausible.
    a = AnuncioOpenClaw(url_anuncio="https://portal/9")
    assert a.precio is None
    assert a.moneda is None
    assert a.superficie_util_m2 is None
    assert a.habitaciones is None


def test_sobre_recibe_anuncios_crudos_para_validacion_por_anuncio():
    # El sobre no valida los anuncios (se validan uno a uno en la ingesta, 2A).
    sobre = SobreScraping(
        job_id="j", portal_url="https://p", fecha_extraccion_utc="2026-07-14T00:00:00Z",
        total_anuncios_extraidos=2, extraccion_completa=True,
        anuncios=[{"url_anuncio": "ok"}, {"campo_roto": 1}],  # el 2º es inválido
    )
    assert len(sobre.anuncios) == 2  # crudos; se filtran luego


def test_prompt_incluye_regla_null_y_esquema():
    from decimal import Decimal
    from uuid import uuid4

    from backend.modelos.configuracion import Portal
    from backend.modelos.pipeline import Busqueda

    portal = Portal(id=uuid4(), nombre="Idealista", url_raiz="https://idealista.com", pais="ES")
    busqueda = Busqueda(
        id=uuid4(), portal_id=portal.id, ciudad="Valencia",
        presupuesto_max=Decimal("200000"), moneda="EUR", tipo_inmueble="PISO",
    )
    prompt = constructor_prompt.construir(busqueda, portal, 50, "job-123")
    assert "null` ANTES QUE INVENCIÓN" in prompt or "null` antes que invención" in prompt.lower()
    assert "job-123" in prompt
    assert "url_anuncio" in prompt  # el esquema está embebido
    assert "50 anuncios" in prompt
