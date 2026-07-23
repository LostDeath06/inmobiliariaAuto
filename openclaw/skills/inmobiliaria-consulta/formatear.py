#!/usr/bin/env python3
"""Convierte las respuestas JSON de la API en texto legible.

Va aparte del script de shell a propósito: incrustar Python dentro de comillas
simples de bash obliga a escapar cada comilla y lo vuelve ilegible.

Lee el JSON por stdin y escribe texto por stdout:

    consultar.sh ranking ES  ->  curl ... | formatear.py ranking --bruto false

El agente lee este texto y lo redacta en lenguaje natural. Por eso el texto
lleva los avisos ya explicados ("el score puede estar infra-penalizado") en vez
de códigos crudos: lo que no se explique aquí, el agente no lo sabrá decir.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter


# La salida lleva acentos y «·». Si el VPS arranca el agente con locale C, Python
# escogería ASCII y esto reventaría con UnicodeEncodeError en mitad de una
# respuesta. Forzar UTF-8 aquí quita esa dependencia del entorno.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass


def _cargar() -> object:
    texto = sys.stdin.read().strip()
    if not texto:
        return None
    try:
        return json.loads(texto)
    except json.JSONDecodeError as e:
        sys.exit(f"La API no devolvió JSON válido: {e}")


def perfiles(datos: list[dict], _a) -> None:
    if not datos:
        print("No hay perfiles de inversor configurados.")
        return
    for p in datos:
        marca = "  (predeterminado)" if p.get("es_predeterminado") else ""
        print(f'{p["nombre"]}{marca}  id={p["id"]}')


def perfil_id(datos: list[dict], a) -> None:
    """Resuelve un perfil por nombre parcial; si no, el predeterminado."""
    buscado = (a.buscado or "").strip().lower()
    elegido = None
    if buscado:
        elegido = next((p for p in datos if buscado in p["nombre"].lower()), None)
    if elegido is None:
        elegido = next((p for p in datos if p.get("es_predeterminado")), None)
    if elegido is None and datos:
        elegido = datos[0]
    if elegido is None:
        sys.exit("No hay perfiles configurados en el sistema.")
    print(elegido["id"])


def ranking(datos: list[dict], a) -> None:
    if not datos:
        print("Sin inmuebles en el ranking con esos filtros.")
        print("Puede que el país no tenga configuración de mercado cargada "
              "(consulta el estado por país) o que no se haya ejecutado ninguna búsqueda.")
        return
    usa_bruto = a.bruto == "true"
    print(f"{len(datos)} inmuebles, ordenados por score "
          f"{'bruto (sin riesgo país)' if usa_bruto else 'total'}:")
    for i, f in enumerate(datos, 1):
        score = f.get("score_bruto") if usa_bruto else f.get("score_total")
        sup = f.get("superficie_util_m2") or f.get("superficie_construida_m2")
        print(f'\n{i}. score {score} [calidad del dato: {f.get("estado_calidad")}]')
        print(f'   {f.get("titulo")}')
        print(f'   {f.get("ciudad")} ({f.get("pais")}) · {f.get("precio")} {f.get("moneda")} · {sup} m2')
        print(f'   id={f.get("inmueble_id")}')
        for aviso in _avisos(f):
            print(f"   AVISO: {aviso}")


def _avisos(f: dict) -> list[str]:
    avisos = []
    if f.get("perfil_zona") == "TURISTICA":
        avisos.append(
            "zona turística: la inversión ahí es de plusvalía y corta estancia, "
            "así que un score de cashflow bajo no significa mala inversión"
        )
    if (f.get("desglose") or {}).get("senales_no_reconocidas"):
        avisos.append(
            "el analista emitió señales que el catálogo del país no contempla y no "
            "se aplicaron: el score puede estar infra-penalizado (mejor de lo real)"
        )
    if f.get("usa_parametros_provisionales"):
        avisos.append("calculado con parámetros provisionales, sin fuente validada")
    if f.get("posible_duplicado_cross_portal"):
        avisos.append("posible duplicado del mismo inmueble en otro portal")
    return avisos


def inmueble(datos: dict, _a) -> None:
    inm = datos.get("inmueble") or {}
    zona = datos.get("zona") or {}
    an = datos.get("analisis")
    met = datos.get("metricas")

    print(inm.get("titulo") or "(sin título)")
    ubic = " ".join(x for x in [inm.get("barrio"), inm.get("ciudad")] if x)
    print(f'  {ubic} ({inm.get("pais")}) · {inm.get("precio")} {inm.get("moneda")}')
    print(f'  {inm.get("superficie_util_m2")} m2 útiles · {inm.get("habitaciones")} habitaciones '
          f'· anunciante {inm.get("tipo_anunciante")}')
    print(f'  calidad del dato: {inm.get("estado_calidad")}')
    print(f'  anuncio: {inm.get("url_anuncio")}')

    if zona.get("perfil_zona") == "TURISTICA":
        print("  AVISO: zona turística. El score de cashflow (larga estancia, apalancado) "
              "no es representativo aquí; la inversión es de plusvalía o corta estancia.")

    for s in datos.get("scores") or []:
        print(f'  score bruto {s.get("score_bruto")} / total {s.get("score_total")} '
              f'[{s.get("estado_calidad")}]')
        if s.get("motivo_descarte"):
            print(f'    DESCARTADO por riesgo eliminatorio: {", ".join(s["motivo_descarte"])}')
        if s.get("usa_parametros_provisionales"):
            print("    calculado con parámetros provisionales")

    if an:
        print(f'  análisis cualitativo: conservación {an.get("estado_conservacion")}, '
              f'reforma {an.get("nivel_reforma_estimado")}, tipología {an.get("tipologia")}, '
              f'apto alquiler larga estancia {an.get("apto_alquiler_larga_estancia")}, '
              f'confianza {an.get("nivel_confianza")}')
        if an.get("senales_riesgo"):
            print(f'    riesgos: {", ".join(an["senales_riesgo"])}')
        if an.get("senales_oportunidad"):
            print(f'    oportunidades: {", ".join(an["senales_oportunidad"])}')
        if an.get("senales_no_reconocidas"):
            print(f'    SEÑALES FUERA DE CATÁLOGO, no aplicadas al score: '
                  f'{", ".join(an["senales_no_reconocidas"])}. El score puede estar infra-penalizado.')
        if an.get("resumen_analista"):
            print(f'    resumen del analista: {an["resumen_analista"]}')
    else:
        print("  sin análisis cualitativo (pendiente o fallido)")

    if met and met.get("metricas"):
        print("  métricas financieras:")
        for k, v in met["metricas"].items():
            print(f"    {k} = {v}")
        if met.get("conversion_parcial"):
            print("    AVISO: conversión de divisa incompleta, falta un tipo de cambio.")


def historico(datos: list[dict], _a) -> None:
    if not datos or len(datos) < 2:
        print("Solo hay un punto de precio: todavía no hay serie con la que comparar.")
        return
    print("Histórico de precios (moneda nativa del anuncio):")
    for p in datos:
        print(f'  {p.get("fecha_detectada")}: {p.get("precio")}')
    primero, ultimo = datos[0].get("precio"), datos[-1].get("precio")
    try:
        variacion = (float(ultimo) - float(primero)) / float(primero) * 100
        print(f"  variación desde el primer registro: {variacion:+.1f}%")
    except (TypeError, ValueError, ZeroDivisionError):
        pass


def inventario(datos: list[dict], _a) -> None:
    if not datos:
        print("No hay ningún inmueble cargado en el sistema.")
        return
    por_pais = Counter(i.get("pais") or "(sin país)" for i in datos)
    print(f"Total de inmuebles: {len(datos)}")
    for pais, n in sorted(por_pais.items(), key=lambda x: -x[1]):
        ciudades = Counter(
            i.get("ciudad") or "(sin ciudad)"
            for i in datos
            if (i.get("pais") or "(sin país)") == pais
        )
        detalle = ", ".join(f"{c}: {k}" for c, k in ciudades.most_common())
        print(f"  {pais}: {n} inmuebles ({detalle})")


def estado_pais(datos, _a) -> None:
    for e in (datos if isinstance(datos, list) else [datos]):
        estado = "OPERATIVO" if e.get("operativo") else "NO operativo"
        print(f'\n{e.get("pais")}: {estado}')
        for it in e.get("items") or []:
            marca = "OK   " if it.get("ok") else "FALTA"
            prov = " (provisional, sin validar)" if it.get("provisional") else ""
            print(f'  [{marca}] {it.get("clave")}{prov}: {it.get("detalle")}')
            if it.get("advertencia"):
                print(f'      ADVERTENCIA: {it["advertencia"]}')


def jobs(datos: list[dict], _a) -> None:
    if not datos:
        print("No hay jobs todavía. Un job se crea al ejecutar una búsqueda.")
        return
    fallidos = [j for j in datos if j.get("estado") == "FALLIDO"]
    print(f"{len(datos)} jobs · {len(fallidos)} fallidos")
    for j in datos[:20]:
        print(f'\n{str(j.get("id"))[:8]} · {j.get("estado")} '
              f'· válidos={j.get("total_anuncios_validos")} '
              f'· cuarentena={j.get("total_anuncios_cuarentena")} '
              f'· coste_usd={j.get("coste_estimado_usd")}')
        if j.get("error_mensaje"):
            crudo = " ".join(str(j["error_mensaje"]).split())
            print(f"   MOTIVO DEL FALLO: {crudo[:800]}")


def senales(datos: list[dict], _a) -> None:
    if not datos:
        print("Ningún inmueble tiene señales fuera de catálogo. Todo lo que emitió "
              "el analista cruzó contra el catálogo de su país.")
        return
    print(f"{len(datos)} inmuebles con señales que el catálogo del país no contempla. "
          "En todos ellos el score puede estar infra-penalizado:")
    for f in datos:
        print(f'  {f.get("titulo")} ({f.get("ciudad")}, {f.get("pais")}): '
              f'{", ".join(f.get("senales_no_reconocidas") or [])} · id={f.get("inmueble_id")}')


def salud(datos, _a) -> None:
    print(json.dumps(datos, ensure_ascii=False, indent=2))


VISTAS = {
    "perfiles": perfiles,
    "perfil-id": perfil_id,
    "ranking": ranking,
    "inmueble": inmueble,
    "historico": historico,
    "inventario": inventario,
    "estado-pais": estado_pais,
    "jobs": jobs,
    "senales": senales,
    "salud": salud,
}


def main() -> None:
    p = argparse.ArgumentParser(description="Formatea las respuestas de la API de consulta.")
    p.add_argument("vista", choices=sorted(VISTAS))
    p.add_argument("--bruto", default="false", help="ranking: usar score bruto")
    p.add_argument("--buscado", default="", help="perfil-id: nombre parcial del perfil")
    a = p.parse_args()

    datos = _cargar()
    if datos is None:
        sys.exit("La API no devolvió nada.")
    VISTAS[a.vista](datos, a)


if __name__ == "__main__":
    main()
