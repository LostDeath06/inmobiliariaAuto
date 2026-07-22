"""Ingesta y normalización (pasos 3-4 del pipeline).

Recibe el sobre validado de OpenClaw. Por CADA anuncio (validación 2A):
- Si valida contra el contrato §5.4 → se guarda en `anuncios_crudos` (inmutable) y
  se normaliza a `inmuebles` (dedup intra-portal, histórico de precios, bandera de
  posible duplicado cross-portal).
- Si NO valida → va a `anuncios_cuarentena` (consultable en el monitor de jobs).

Nunca inventa datos: campo ausente → NULL. Nunca aborta el lote por un fallo
individual.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation
from uuid import UUID

from pydantic import ValidationError

from ..modelos.enumeraciones import CalidadDato
from ..modelos.openclaw import AnuncioOpenClaw, SobreScraping
from ..repositorios import (
    anuncios as repo_anuncios,
    inmuebles as repo_inmuebles,
    jobs as repo_jobs,
    portales as repo_portales,
)


def _hash(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _a_decimal(valor) -> Decimal | None:
    if valor is None:
        return None
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return None


def _fecha(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        return datetime.fromisoformat(valor.replace("Z", "+00:00"))
    except ValueError:
        return None


async def _normalizar_anuncio(
    anuncio: AnuncioOpenClaw, portal_id: UUID, pais_portal: str | None
) -> UUID:
    """Inserta o actualiza el inmueble normalizado. Devuelve su id."""
    hash_dedup = _hash(anuncio.url_anuncio)
    precio = _a_decimal(anuncio.precio)
    sup_util = _a_decimal(anuncio.superficie_util_m2)
    sup_const = _a_decimal(anuncio.superficie_construida_m2)
    pais = anuncio.pais or pais_portal

    # Calidad a nivel de dato: sin precio o superficie → NO_CALCULABLE.
    superficie = sup_util or sup_const
    estado = CalidadDato.NO_CALCULABLE if (precio is None or superficie is None) else CalidadDato.COMPLETO

    datos = {
        "portal_id": portal_id,
        "id_portal": anuncio.id_portal,
        "url_anuncio": anuncio.url_anuncio,
        "hash_deduplicacion": hash_dedup,
        "titulo": anuncio.titulo,
        "precio": precio,
        "moneda": anuncio.moneda,
        "superficie_construida_m2": sup_const,
        "superficie_util_m2": sup_util,
        "habitaciones": anuncio.habitaciones,
        "banos": anuncio.banos,
        "planta": anuncio.planta,
        "tiene_ascensor": anuncio.tiene_ascensor,
        "ano_construccion": anuncio.ano_construccion,
        "certificado_energetico": anuncio.certificado_energetico,
        "direccion_texto": anuncio.direccion_texto,
        "barrio": anuncio.barrio,
        "ciudad": anuncio.ciudad,
        "provincia": anuncio.provincia,
        "pais": pais,
        "codigo_postal": anuncio.codigo_postal,
        "latitud": _a_decimal(anuncio.latitud),
        "longitud": _a_decimal(anuncio.longitud),
        "descripcion_completa": anuncio.descripcion_completa,
        "caracteristicas_listadas": anuncio.caracteristicas_listadas,
        "urls_imagenes": anuncio.urls_imagenes,
        "tipo_anunciante": anuncio.tipo_anunciante.value if anuncio.tipo_anunciante else None,
        "fecha_publicacion": _fecha(anuncio.fecha_publicacion),
        "gastos_comunidad_mes": _a_decimal(anuncio.gastos_comunidad_mes),
        "estado_calidad": estado.value,
    }

    existente = await repo_inmuebles.obtener_por_hash(portal_id, hash_dedup)
    if existente is None:
        inmueble = await repo_inmuebles.insertar(datos)
        if precio is not None:
            await repo_inmuebles.registrar_precio(inmueble.id, precio, anuncio.moneda)
    else:
        inmueble = existente
        # Historial de precio: registra bajadas/subidas (señal de inversión).
        if precio is not None and existente.precio is not None and precio != existente.precio:
            await repo_inmuebles.registrar_precio(existente.id, precio, anuncio.moneda)
        await repo_inmuebles.actualizar(existente.id, datos)

    # Bandera de posible duplicado cross-portal (3A): se marca, no se fusiona.
    candidatos = await repo_inmuebles.buscar_candidatos_duplicado(
        pais=pais, ciudad=anuncio.ciudad, precio=precio, superficie=superficie,
        excluir_portal=portal_id,
    )
    if candidatos:
        await repo_inmuebles.marcar_posible_duplicado(
            inmueble.id, [c.id for c in candidatos]
        )
    return inmueble.id


async def procesar(job_id: UUID, sobre: SobreScraping) -> dict:
    """Procesa el sobre. Devuelve un resumen (válidos, cuarentena, ids)."""
    job = await repo_jobs.obtener(job_id)
    if job is None:
        raise ValueError(f"Job {job_id} no existe")
    from ..repositorios import busquedas as repo_busquedas
    busqueda = await repo_busquedas.obtener(job.busqueda_id)
    portal = await repo_portales.obtener(busqueda.portal_id) if busqueda else None
    if portal is None:
        raise ValueError("Portal del job no encontrado")

    validos = 0
    cuarentena = 0
    ids_inmuebles: list[UUID] = []

    for crudo in sobre.anuncios:
        try:
            anuncio = AnuncioOpenClaw.model_validate(crudo)
        except ValidationError as e:
            cuarentena += 1
            await repo_anuncios.guardar_en_cuarentena(
                job_id=job_id,
                url_anuncio=crudo.get("url_anuncio") if isinstance(crudo, dict) else None,
                payload_crudo=crudo if isinstance(crudo, dict) else {"_raw": str(crudo)},
                errores_validacion=json.loads(e.json()),
            )
            continue

        validos += 1
        # anuncios_crudos: inmutable, append-only, fuente de verdad auditable.
        payload = anuncio.model_dump()
        await repo_anuncios.guardar_crudo(
            job_id=job_id, url_anuncio=anuncio.url_anuncio,
            payload_json=payload,
            hash_contenido=_hash(json.dumps(payload, sort_keys=True, default=str)),
        )
        ids_inmuebles.append(
            await _normalizar_anuncio(anuncio, portal.id, portal.pais)
        )

    # Estado del job: PARCIAL si hubo cuarentena o extracción incompleta.
    estado = "COMPLETADO"
    if cuarentena > 0 or not sobre.extraccion_completa:
        estado = "PARCIAL"
    await repo_jobs.actualizar(job_id, {
        "estado": estado,
        "total_resultados_detectados": sobre.total_resultados_detectados,
        "total_anuncios_extraidos": sobre.total_anuncios_extraidos,
        "total_anuncios_validos": validos,
        "total_anuncios_cuarentena": cuarentena,
        "extraccion_completa": sobre.extraccion_completa,
        "finalizado_en": datetime.utcnow(),
    })

    return {
        "job_id": str(job_id), "estado": estado, "validos": validos,
        "cuarentena": cuarentena, "inmuebles": [str(i) for i in ids_inmuebles],
    }
