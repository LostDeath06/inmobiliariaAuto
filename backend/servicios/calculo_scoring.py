"""Servicio de scoring.

Extrae los componentes crudos (a partir de métricas + análisis + benchmarks +
histórico), comprueba los riesgos eliminatorios (descarte duro), construye las
curvas de normalización desde la configuración del país, llama al motor de scoring
(función pura) y persiste un score por cada perfil.

Los componentes limitados por datos (calidad_zona, margen_reforma) usan proxies
MVP documentados; ninguno introduce constantes de negocio (los anclajes vienen de
la configuración del país). Un componente sin datos → None → el motor redistribuye
su peso y marca PARCIAL.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from uuid import UUID

from ..dominio import motor_scoring
from ..modelos.analisis import AnalisisCualitativo
from ..modelos.configuracion import PerfilInversor
from ..modelos.enumeraciones import CalidadDato, EstadoParametro
from ..modelos.pipeline import Inmueble
from ..repositorios import (
    analisis as repo_analisis,
    configuracion_pais,
    inmuebles as repo_inmuebles,
    perfiles as repo_perfiles,
    scores as repo_scores,
)
from . import calculo_financiero

_APTO = {"SI": Decimal("1"), "DUDOSO": Decimal("0.5"), "NO": Decimal("0")}
_REFORMABLE = {"COSMETICA", "MEDIA", "INTEGRAL"}


def _huella_pesos(pesos: dict) -> str:
    return hashlib.sha256(
        json.dumps(pesos, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]


def ajustar_por_senales_ignoradas(
    estado_calidad: CalidadDato, desglose: dict, senales_no_reconocidas: list[str]
) -> tuple[CalidadDato, dict]:
    """Blindaje: un score con señales ignoradas NUNCA puede presentarse como COMPLETO.

    Si el analista emitió códigos que el catálogo del país no contempla, esas señales
    no cruzaron con nada: ni descarte duro ni penalización ponderable. El score sale
    igualmente, y encima sale *mejor* de lo que debería — `riesgo_activo` sin
    penalizaciones puntúa como "sin riesgo alguno" (máximo). Es decir: el fallo empuja
    al alza, justo en la dirección peligrosa para quien decide comprar.

    Por eso se degrada a PARCIAL: el propietario no puede ver un COMPLETO limpio en el
    ranking sobre un inmueble cuyo riesgo no se evaluó. Los códigos van al desglose para
    poder explicar el porqué en la ficha.

    No toca DESCARTADO_RIESGO ni NO_CALCULABLE: ya son estados que no invitan a confiar.
    Función pura.
    """
    if not senales_no_reconocidas:
        return estado_calidad, desglose
    nuevo = dict(desglose)
    nuevo["senales_no_reconocidas"] = list(senales_no_reconocidas)
    if estado_calidad == CalidadDato.COMPLETO:
        return CalidadDato.PARCIAL, nuevo
    return estado_calidad, nuevo


async def _riesgos(inmueble: Inmueble, analisis: AnalisisCualitativo | None):
    """Devuelve (eliminatorios_presentes, penalizacion_ponderable | None)."""
    pais = inmueble.pais or ""
    filas = await configuracion_pais.listar_riesgos_pais(pais)
    if not filas or analisis is None:
        # País sin config de riesgos, o sin análisis → no calculable / sin descarte.
        return [], None
    elim = {r.codigo for r in filas if r.es_eliminatorio}
    ponderables = {r.codigo: r.penalizacion for r in filas if not r.es_eliminatorio}

    presentes = set(analisis.senales_riesgo)
    ec = analisis.estado_conservacion.value
    if ec == "RUINA":
        presentes.add("ESTADO_RUINA")
    elif ec == "A_REFORMAR":
        presentes.add("ESTADO_A_REFORMAR")

    eliminatorios_presentes = sorted(presentes & elim)
    penalizacion = Decimal(0)
    for codigo in presentes:
        pen = ponderables.get(codigo)
        if pen is not None:
            penalizacion += pen
    return eliminatorios_presentes, penalizacion


async def _oportunidad_temporal(
    inmueble: Inmueble, analisis: AnalisisCualitativo | None
) -> Decimal | None:
    """B9: <2 puntos de histórico y sin señal cualitativa → None (no 0)."""
    n_hist = await repo_inmuebles.contar_historico(inmueble.id)
    senales = set(analisis.senales_oportunidad) - {"NINGUNA"} if analisis else set()
    if n_hist < 2 and not senales:
        return None
    indice = Decimal(0)
    if n_hist >= 2:
        hist = await repo_inmuebles.listar_historico_precios(inmueble.id)
        if hist and hist[-1].precio < hist[0].precio:
            indice += Decimal("0.5")
    if senales:
        indice += Decimal("0.5")
    return min(indice, Decimal(1))


async def _componentes(
    inmueble: Inmueble,
    analisis: AnalisisCualitativo | None,
    metricas: dict,
    config_pais,
    penalizacion_riesgo: Decimal | None,
) -> dict[str, Decimal | None]:
    sat_rent = config_pais.sat_rentabilidad_neta if config_pais else None
    sat_desc = config_pais.sat_descuento_mercado if config_pais else None

    roi = metricas.get("roi_neto")
    descuento = metricas.get("descuento_mercado")

    # calidad_zona: proxy MVP = rentabilidad bruta media de zona (dato limitado).
    calidad_zona = None
    if inmueble.ciudad:
        from ..repositorios import config_mercado
        bench = await config_mercado.obtener_benchmark_zona(
            inmueble.pais or "", inmueble.ciudad, inmueble.barrio
        )
        if bench and bench.rentabilidad_bruta_media_zona is not None and sat_rent:
            calidad_zona = bench.rentabilidad_bruta_media_zona

    # margen_reforma: proxy MVP: reformable + comprado con descuento.
    margen = None
    if analisis is not None and descuento is not None:
        nivel = analisis.nivel_reforma_estimado.value
        if nivel == "NINGUNA":
            margen = Decimal(0)
        elif nivel in _REFORMABLE:
            margen = descuento

    aptitud = None
    if analisis is not None:
        larga = _APTO.get(analisis.apto_alquiler_larga_estancia.value, Decimal(0))
        turistico = _APTO.get(analisis.apto_alquiler_turistico.value, Decimal(0))
        aptitud = max(larga, turistico)

    return {
        "rentabilidad_neta": roi if sat_rent else None,
        "descuento_mercado": descuento if sat_desc else None,
        "calidad_zona": calidad_zona,
        "margen_reforma": margen if sat_desc else None,
        "aptitud_alquiler": aptitud,
        "riesgo_activo": penalizacion_riesgo,
        "oportunidad_temporal": await _oportunidad_temporal(inmueble, analisis),
    }


def _normalizacion(config_pais) -> dict:
    sat_rent = config_pais.sat_rentabilidad_neta if config_pais else None
    sat_desc = config_pais.sat_descuento_mercado if config_pais else None
    return {
        "rentabilidad_neta": {"min": 0, "max": sat_rent or 1, "direccion": "asc"},
        "descuento_mercado": {"min": 0, "max": sat_desc or 1, "direccion": "asc"},
        "calidad_zona": {"min": 0, "max": sat_rent or 1, "direccion": "asc"},
        "margen_reforma": {"min": 0, "max": sat_desc or 1, "direccion": "asc"},
        "aptitud_alquiler": {"min": 0, "max": 1, "direccion": "asc"},
        "riesgo_activo": {"min": -100, "max": 0, "direccion": "asc"},
        "oportunidad_temporal": {"min": 0, "max": 1, "direccion": "asc"},
    }


def _usa_provisionales(config_pais, componentes: dict) -> bool:
    if config_pais is None:
        return False
    prov = EstadoParametro.PROVISIONAL
    marcas = []
    if config_pais.riesgo_pais_estado == prov and config_pais.riesgo_pais:
        marcas.append(True)
    if componentes.get("rentabilidad_neta") is not None and \
            config_pais.sat_rentabilidad_estado == prov:
        marcas.append(True)
    if componentes.get("descuento_mercado") is not None and \
            config_pais.sat_descuento_estado == prov:
        marcas.append(True)
    if componentes.get("rentabilidad_neta") is not None and \
            config_pais.tipo_interes_estado == prov:
        marcas.append(True)
    return any(marcas)


async def calcular_score_perfil(
    inmueble: Inmueble, analisis: AnalisisCualitativo | None, perfil: PerfilInversor
):
    """Calcula y persiste el score de un inmueble para un perfil."""
    pais = inmueble.pais or ""
    config_pais = await configuracion_pais.obtener_config_mercado(pais)
    riesgo_pais = config_pais.riesgo_pais if config_pais else Decimal(0)

    no_reconocidas = list(analisis.senales_no_reconocidas) if analisis else []

    # 1. Riesgos eliminatorios → descarte duro (precede al scoring).
    eliminatorios, penalizacion = await _riesgos(inmueble, analisis)
    if eliminatorios:
        estado_desc, desglose_desc = ajustar_por_senales_ignoradas(
            CalidadDato.DESCARTADO_RIESGO, {"descartado_por": eliminatorios}, no_reconocidas
        )
        return await repo_scores.guardar(
            inmueble_id=inmueble.id, perfil_id=perfil.id,
            score_bruto=None, score_total=None, riesgo_pais_aplicado=riesgo_pais,
            desglose=desglose_desc,
            estado_calidad=estado_desc,
            motivo_descarte=eliminatorios, usa_parametros_provisionales=False,
            version_pesos=_huella_pesos(perfil.pesos),
        )

    # 2. Métricas (en memoria, con los supuestos de este perfil).
    resultado = await calculo_financiero.calcular(inmueble, analisis, perfil)
    metricas = resultado.metricas

    # 3. Componentes crudos + normalización + scoring.
    componentes = await _componentes(inmueble, analisis, metricas, config_pais, penalizacion)
    normalizacion = _normalizacion(config_pais)
    res = motor_scoring.calcular_score(componentes, perfil.pesos, normalizacion, riesgo_pais)

    provisional = _usa_provisionales(config_pais, componentes)

    # Umbral de descarte (por perfil, país): marca (no excluye del guardado).
    umbral = await configuracion_pais.obtener_umbrales(perfil.id, pais)
    desglose = dict(res.desglose)
    if umbral and res.score_total is not None:
        desglose["bajo_umbral_descarte"] = bool(res.score_total < umbral.score_descarte)
        desglose["score_descarte"] = str(umbral.score_descarte)

    # Blindaje: si hubo señales que el catálogo del país no contempla, no se aplicaron
    # y el score puede estar infra-penalizado → nunca COMPLETO (§ ajustar_por_senales_ignoradas).
    estado_final, desglose = ajustar_por_senales_ignoradas(
        res.estado_calidad, desglose, no_reconocidas
    )

    return await repo_scores.guardar(
        inmueble_id=inmueble.id, perfil_id=perfil.id,
        score_bruto=res.score_bruto, score_total=res.score_total,
        riesgo_pais_aplicado=riesgo_pais, desglose=desglose,
        estado_calidad=estado_final, motivo_descarte=[],
        usa_parametros_provisionales=provisional,
        version_pesos=_huella_pesos(perfil.pesos),
    )


async def calcular_todos_los_perfiles(inmueble_id: UUID) -> list:
    """Calcula el score de un inmueble bajo todos los perfiles activos."""
    inmueble = await repo_inmuebles.obtener(inmueble_id)
    if inmueble is None:
        return []
    analisis = await repo_analisis.obtener(inmueble_id)
    resultados = []
    for perfil in await repo_perfiles.listar(solo_activos=True):
        resultados.append(await calcular_score_perfil(inmueble, analisis, perfil))
    return resultados
