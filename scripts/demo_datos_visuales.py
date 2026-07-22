"""Datos de DEMO para revisar la capa visual (Ranking y Ficha). NO SON DATOS REALES.

ATENCIÓN — esto NO viola la línea roja #3 ("no se inventan datos"), pero conviene
entender qué es cada cosa:

- Las CIFRAS que se ven en pantalla NO las inventa este script: las calculan el motor
  financiero y el de scoring REALES a partir de estos inputs. Lo que se ve es salida
  auténtica de los motores.
- Los INPUTS (precios de anuncios, benchmarks de zona, gastos, costes de reforma) sí
  son ficticios: son un decorado para poder revisar el diseño. Van marcados con
  `fuente='DEMO'` y el portal se llama 'DEMO Visual'.
- El juicio cualitativo de Claude se simula (aquí no hay API key), pero se inserta
  pasando por `validar_senales` — el mismo camino que la salida real del modelo.

Uso:
    python scripts/demo_datos_visuales.py            # siembra
    python scripts/demo_datos_visuales.py --purgar   # borra TODO lo que sembró

Purga siempre antes de cargar datos reales: si estos benchmarks se quedan, el sistema
daría por operativo un país con datos de mentira, que es justo lo que no queremos.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from backend.modelos.analisis import AnalisisCualitativo  # noqa: E402
from backend.modelos.enumeraciones import (  # noqa: E402
    AptoTernario, CalidadDescripcion, CoherenciaPrecio, EstadoConservacion,
    NivelConfianza, NivelReforma, Tipologia, TipoGastoAdquisicion,
)
from backend.nucleo import basedatos  # noqa: E402
from backend.repositorios import (  # noqa: E402
    analisis as repo_analisis,
    config_mercado,
    configuracion_pais,
    inmuebles as repo_inmuebles,
    perfiles as repo_perfiles,
)
from backend.servicios import calculo_financiero, calculo_scoring  # noqa: E402
from backend.servicios.analista_cualitativo import validar_senales  # noqa: E402

PORTAL_DEMO = "DEMO Visual"
FUENTE = "DEMO"

# Decorado de mercado (ficticio). Marcado con fuente='DEMO'.
COSTES = [(NivelReforma.COSMETICA, 450), (NivelReforma.MEDIA, 800), (NivelReforma.INTEGRAL, 1200)]
GASTOS = [
    ("ITP", TipoGastoAdquisicion.PORCENTAJE, Decimal("0.10")),
    ("NOTARIA", TipoGastoAdquisicion.FIJO, Decimal("1200")),
    ("REGISTRO", TipoGastoAdquisicion.FIJO, Decimal("600")),
]
# ciudad -> (€/m² venta, €/m²/mes alquiler, rentabilidad bruta media de zona)
ZONAS = {
    "Madrid": (Decimal("4200"), Decimal("16.5"), Decimal("0.047")),
    "Valencia": (Decimal("2300"), Decimal("11.2"), Decimal("0.058")),
    "Bilbao": (Decimal("3100"), Decimal("12.8"), Decimal("0.050")),
}

# (titulo, ciudad, barrio, precio, m2, hab, estado, reforma, riesgos, oportunidades)
CATALOGO_DEMO = [
    ("Piso reformado en Chamberí, exterior con ascensor", "Madrid", "Chamberí",
     320000, 78, 2, EstadoConservacion.REFORMADO, NivelReforma.NINGUNA, [], ["PARTICULAR_SIN_AGENCIA"]),
    ("Piso a reformar en Vallecas, buena altura", "Madrid", "Puente de Vallecas",
     145000, 65, 3, EstadoConservacion.A_REFORMAR, NivelReforma.MEDIA, ["CARGAS"], ["REFORMABLE_CON_MARGEN"]),
    ("Ático reformado en Ruzafa con terraza", "Valencia", "Ruzafa",
     189000, 82, 3, EstadoConservacion.REFORMADO, NivelReforma.NINGUNA, [], []),
    ("Vivienda en Benimaclet, precio rebajado", "Valencia", "Benimaclet",
     132000, 70, 3, EstadoConservacion.BUEN_ESTADO, NivelReforma.COSMETICA, [], ["PRECIO_REBAJADO", "VENTA_URGENTE"]),
    ("Piso señorial en Indautxu, finca rehabilitada", "Bilbao", "Indautxu",
     275000, 90, 3, EstadoConservacion.BUEN_ESTADO, NivelReforma.NINGUNA, [], []),
    ("Oportunidad en Latina, procedente de subasta", "Madrid", "Latina",
     168000, 72, 2, EstadoConservacion.A_REFORMAR, NivelReforma.INTEGRAL, ["SUBASTA"], ["REFORMABLE_CON_MARGEN"]),
    ("Obra nueva en Campanar, entrega inmediata", "Valencia", "Campanar",
     210000, 95, 3, EstadoConservacion.OBRA_NUEVA, NivelReforma.NINGUNA, [], []),
    # Este trae un código FUERA de catálogo → demo de `senales_no_reconocidas`.
    ("Piso en Deusto junto a la ría, a actualizar", "Bilbao", "Deusto",
     198000, 85, 3, EstadoConservacion.A_REFORMAR, NivelReforma.MEDIA,
     ["HUMEDADES_ESTRUCTURALES"], ["HERENCIA"]),
    ("Piso reformado en Tetuán, proindiviso", "Madrid", "Tetuán",
     240000, 68, 2, EstadoConservacion.REFORMADO, NivelReforma.NINGUNA, ["PROINDIVISO"], ["HERENCIA"]),
    # Riesgo eliminatorio → DESCARTADO_RIESGO (no sale en ranking; sí en su ficha).
    ("Vivienda en Patraix, ocupada", "Valencia", "Patraix",
     119000, 60, 3, EstadoConservacion.RUINA, NivelReforma.INTEGRAL, ["OKUPAS"], []),
]


async def _purgar() -> None:
    portal = await basedatos.obtener_uno("SELECT id FROM portales WHERE nombre = $1", PORTAL_DEMO)
    if portal:
        # analisis/metricas/scores/historico caen por ON DELETE CASCADE.
        n = await basedatos.ejecutar("DELETE FROM inmuebles WHERE portal_id = $1", portal["id"])
        print(f"  - inmuebles demo borrados ({n})")
        await basedatos.ejecutar("DELETE FROM portales WHERE id = $1", portal["id"])
        print("  - portal demo borrado")
    for tabla in ("benchmarks_zona", "gastos_adquisicion"):
        n = await basedatos.ejecutar(f"DELETE FROM {tabla} WHERE fuente = $1", FUENTE)
        print(f"  - {tabla}: {n}")
    # costes_reforma es un esqueleto sembrado: se devuelve a NULL, no se borra la fila.
    await basedatos.ejecutar(
        "UPDATE costes_reforma SET coste_m2 = NULL, fuente = NULL WHERE fuente = $1", FUENTE
    )
    print("  - costes_reforma devueltos a NULL")


async def _sembrar_config() -> None:
    for nivel, coste in COSTES:
        await config_mercado.establecer_coste_reforma(
            "ES", nivel, Decimal(coste), "EUR", FUENTE
        )
    for concepto, tipo, valor in GASTOS:
        await config_mercado.establecer_gasto_adquisicion(
            pais="ES", region="", concepto=concepto, tipo=tipo.value,
            valor=valor, moneda="EUR", fuente=FUENTE,
        )
    for ciudad, (venta, alquiler, rent) in ZONAS.items():
        await config_mercado.establecer_benchmark(
            pais="ES", ciudad=ciudad, barrio=None, moneda="EUR",
            precio_m2_venta_medio=venta, precio_m2_alquiler_medio=alquiler,
            rentabilidad_bruta_media_zona=rent, fuente=FUENTE, fecha_dato=date.today(),
        )
    print(f"  + config de mercado ES (fuente={FUENTE})")


def _analisis_demo(estado, reforma, riesgos, oportunidades) -> AnalisisCualitativo:
    return AnalisisCualitativo(
        estado_conservacion=estado,
        nivel_reforma_estimado=reforma,
        tipologia=Tipologia.PISO,
        senales_riesgo=list(riesgos),
        senales_oportunidad=list(oportunidades),
        apto_alquiler_larga_estancia=AptoTernario.SI,
        apto_alquiler_turistico=AptoTernario.DUDOSO if estado != EstadoConservacion.RUINA else AptoTernario.NO,
        potencial_division_horizontal=AptoTernario.NO,
        calidad_descripcion=CalidadDescripcion.ESTANDAR,
        coherencia_precio_descripcion=CoherenciaPrecio.COHERENTE,
        resumen_analista="Análisis de DEMO para revisión visual; no procede de Claude.",
        nivel_confianza=NivelConfianza.MEDIA,
        campos_no_inferibles=[],
    )


async def _sembrar() -> None:
    await _sembrar_config()

    portal = await basedatos.obtener_uno(
        "INSERT INTO portales (nombre, url_raiz, pais, activo) VALUES ($1,$2,$3,TRUE) "
        "ON CONFLICT (url_raiz) DO UPDATE SET nombre = EXCLUDED.nombre RETURNING id",
        PORTAL_DEMO, "https://demo.local", "ES",
    )
    portal_id = portal["id"]

    # Códigos válidos del país: los mismos que el pipeline entrega al analista.
    riesgos_pais = [r.codigo for r in await configuracion_pais.listar_riesgos_pais("ES")]
    catalogo = await configuracion_pais.listar_catalogo_riesgos()
    oport_pais = [c.codigo for c in catalogo if c.clase.value == "OPORTUNIDAD"]

    perfil_pred = await repo_perfiles.obtener_predeterminado()
    creados = []

    for (titulo, ciudad, barrio, precio, m2, hab, estado, reforma, riesgos, oportunidades) in CATALOGO_DEMO:
        inm = await repo_inmuebles.insertar({
            "portal_id": portal_id,
            "url_anuncio": f"https://demo.local/{uuid4().hex[:10]}",
            "hash_deduplicacion": uuid4().hex,
            "titulo": titulo,
            "precio": Decimal(precio),
            "moneda": "EUR",
            "superficie_util_m2": Decimal(m2),
            "superficie_construida_m2": Decimal(m2) + Decimal(8),
            "habitaciones": hab,
            "banos": 1,
            "barrio": barrio,
            "ciudad": ciudad,
            "provincia": ciudad,
            "pais": "ES",
            "descripcion_completa": titulo,
            "tipo_anunciante": "AGENCIA",
            "gastos_comunidad_mes": Decimal("55"),
            "estado_calidad": "COMPLETO",
        })

        # Histórico: el rebajado trae serie con bajada (alimenta oportunidad_temporal).
        if "PRECIO_REBAJADO" in oportunidades:
            base = datetime.now() - timedelta(days=90)
            for i, p in enumerate([148000, 141000, precio]):
                await basedatos.ejecutar(
                    "INSERT INTO historico_precios (inmueble_id, precio, moneda, fecha_detectada) "
                    "VALUES ($1,$2,$3,$4)",
                    inm.id, Decimal(p), "EUR", base + timedelta(days=i * 40),
                )
        else:
            await repo_inmuebles.registrar_precio(inm.id, Decimal(precio), "EUR")

        # Juicio cualitativo simulado, por el MISMO camino que la salida real de Claude.
        crudo = _analisis_demo(estado, reforma, riesgos, oportunidades)
        validado = validar_senales(crudo, riesgos_pais, oport_pais)
        await repo_analisis.guardar(
            inm.id, validado, hash_contenido=uuid4().hex, modelo="demo-visual (no es Claude)"
        )

        # Motores REALES: métricas + scores.
        analisis = await repo_analisis.obtener(inm.id)
        if perfil_pred:
            await calculo_financiero.calcular_y_guardar(inm, analisis, perfil_pred)
        await calculo_scoring.calcular_todos_los_perfiles(inm.id)
        creados.append((titulo, validado.senales_no_reconocidas))

    print(f"  + {len(creados)} inmuebles demo con metricas y scores calculados por los motores")
    for titulo, no_rec in creados:
        if no_rec:
            print(f"    * '{titulo[:40]}' -> senales_no_reconocidas={no_rec}")


async def main() -> None:
    purgar = "--purgar" in sys.argv
    print("Purgando datos de DEMO…" if purgar else "Sembrando datos de DEMO…")
    try:
        await _purgar()
        if not purgar:
            await _sembrar()
        print("Listo.")
    finally:
        await basedatos.cerrar_pool()


if __name__ == "__main__":
    asyncio.run(main())
