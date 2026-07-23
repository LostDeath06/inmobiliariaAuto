#!/usr/bin/env python3
"""Carga la configuración fiscal investigada de ES, DO y VE — vía API.

TODO lo que carga va marcado PROVISIONAL con su fuente, salvo lo que la fuente
respalda de verdad. Nada aquí es criterio de inversión: son datos fiscales
públicos que el motor necesita para calcular el coste de adquisición.

LO QUE NO CARGA, A PROPÓSITO:
  - Costes de reforma (€/m²): muy variables por zona y calidad. Van con
    presupuesto real de contratista, no con una media inventada.
  - Benchmarks de zona: no existen en fuente única para toda España. Van por
    barrio, y solo de donde se vaya a operar.
  - Catálogo de riesgos de DO y VE: necesita criterio legal local.
El sistema ya avisa correctamente de que faltan; rellenarlos a ojo sería peor.

USO
    python scripts/cargar_config_mercado.py                 # carga
    python scripts/cargar_config_mercado.py --purgar        # revierte lo cargado
    python scripts/cargar_config_mercado.py --simular       # enseña qué haría
    python scripts/cargar_config_mercado.py --url http://localhost/api \\
        --usuario admin --password ...                      # contra el VPS

Es IDEMPOTENTE: los endpoints hacen UPSERT sobre (pais, region, concepto), así que
reejecutarlo actualiza en vez de duplicar.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.error
import urllib.request

# Los mensajes llevan acentos y flechas. Sin esto, en una consola con locale
# no-UTF8 el script revienta a mitad de carga y deja la configuración a medias.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

# --- Fuentes (se guardan literalmente en el campo `fuente` de cada fila) ------
FUENTE_ITP_ES = "PROVISIONAL - hipotips.com jun 2026 / idealista - VALIDAR"
FUENTE_FIJOS_ES = "PROVISIONAL - punto medio rango de mercado 2026 - VALIDAR"
FUENTE_DO_IMPUESTO = "DGII Ley 173-07 - VERIFICADO"
FUENTE_DO_RESTO = "PROVISIONAL - VALIDAR"
FUENTE_VE = "PROVISIONAL - ZonaVen abr 2026 / Camara Inmobiliaria VE - VALIDAR"
FUENTE_INTERES_DO = "PROVISIONAL - Banco Central RD promedio 2026 (DOP) - VALIDAR"
FUENTE_REGIONES = "Division administrativa oficial (provincia -> comunidad autonoma)"

# =============================================================================
#  C.1 — España: ITP por comunidad autónoma
# =============================================================================
# LIMITACIÓN CONOCIDA — TIPOS ESCALADOS.
# Aragón, Asturias, Extremadura, Baleares y Cataluña aplican tipos POR TRAMOS de
# precio (suben con el valor del inmueble). Aquí va el tipo del tramo más bajo,
# porque el modelo de `gastos_adquisicion` guarda UN valor por (pais, region,
# concepto) y no soporta tramos. Consecuencia: en esas cinco comunidades, un
# inmueble caro sale con el ITP INFRAESTIMADO, y por tanto con el coste de
# adquisición bajo y el ROI algo alto. Soportar tramos exigiría una tabla hija
# (region, precio_desde, precio_hasta, tipo) y que el motor eligiera el tramo.
#
# CATALUÑA: además tiene un 20% para GRANDES TENEDORES. No se carga: es un caso
# de sujeto, no de inmueble, y el modelo no sabe quién compra.
ITP_ES = [
    ("Pais Vasco", "0.040"),
    ("Madrid", "0.060"),
    ("Navarra", "0.060"),
    ("Ceuta", "0.060"),
    ("Melilla", "0.060"),
    ("Canarias", "0.065"),
    ("Andalucia", "0.070"),
    ("La Rioja", "0.070"),
    ("Castilla y Leon", "0.080"),
    ("Galicia", "0.080"),
    ("Murcia", "0.080"),
    ("Aragon", "0.080"),          # escalado: tramo más bajo
    ("Asturias", "0.080"),        # escalado: tramo más bajo
    ("Extremadura", "0.080"),     # escalado: tramo más bajo
    ("Baleares", "0.080"),        # escalado: tramo más bajo
    ("Cantabria", "0.090"),
    ("Castilla-La Mancha", "0.090"),
    ("Comunidad Valenciana", "0.090"),
    ("Cataluna", "0.100"),        # escalado: tramo más bajo
]

# =============================================================================
#  C.2 — España: gastos fijos, iguales en todas las comunidades (region = "")
# =============================================================================
FIJOS_ES = [
    ("Notaria", "750"),
    ("Registro de la propiedad", "550"),
    ("Gestoria", "400"),
    ("Tasacion", "450"),
]

# =============================================================================
#  C.3 — República Dominicana
# =============================================================================
# El impuesto de transferencia es el que CONFOTUR (Ley 158-01) exime: se marca
# `exento_confotur`. Los otros dos se pagan igual. Que el concepto exento sea un
# dato y no un `if` en Python es lo que respeta el Principio 2.
GASTOS_DO = [
    ("Impuesto de transferencia", "PORCENTAJE", "0.030", True, FUENTE_DO_IMPUESTO),
    ("Honorarios legales/notariales", "PORCENTAJE", "0.0125", False, FUENTE_DO_RESTO),
    ("Gastos de cierre", "PORCENTAJE", "0.010", False, FUENTE_DO_RESTO),
]

# =============================================================================
#  C.4 — Venezuela: UN concepto agregado, no desglosado
# =============================================================================
# La ley venezolana fija un tope del 2% para el arancel de registro, pero la
# Cámara Inmobiliaria documentó que el 25,9% de los compradores pagó un 10% por
# discrecionalidad del registrador. Desglosar "arancel 2% + otros 8%" daría una
# falsa precisión: no sabemos cómo se reparte, solo lo que acaba pagándose.
# Un único concepto agregado dice la verdad de lo que se sabe.
GASTOS_VE = [
    ("Gastos de cierre (agregado)", "PORCENTAJE", "0.100", False, FUENTE_VE),
]

# =============================================================================
#  Mapa provincia -> comunidad autónoma
# =============================================================================
# NO es un extra: sin esto el sistema no sabe qué fila de ITP le toca a un
# inmueble. El anuncio trae `provincia` ("Valencia"), y el ITP está guardado por
# comunidad ("Comunidad Valenciana"). Sin el mapa, el motor no encuentra el gasto
# y marca el inmueble como incompleto (que es correcto, pero inútil).
PROVINCIAS_ES = {
    "Alava": "Pais Vasco", "Araba": "Pais Vasco", "Guipuzcoa": "Pais Vasco",
    "Gipuzkoa": "Pais Vasco", "Vizcaya": "Pais Vasco", "Bizkaia": "Pais Vasco",
    "Madrid": "Madrid",
    "Navarra": "Navarra",
    "Ceuta": "Ceuta",
    "Melilla": "Melilla",
    "Las Palmas": "Canarias", "Santa Cruz de Tenerife": "Canarias",
    "Almeria": "Andalucia", "Cadiz": "Andalucia", "Cordoba": "Andalucia",
    "Granada": "Andalucia", "Huelva": "Andalucia", "Jaen": "Andalucia",
    "Malaga": "Andalucia", "Sevilla": "Andalucia",
    "La Rioja": "La Rioja",
    "Avila": "Castilla y Leon", "Burgos": "Castilla y Leon", "Leon": "Castilla y Leon",
    "Palencia": "Castilla y Leon", "Salamanca": "Castilla y Leon",
    "Segovia": "Castilla y Leon", "Soria": "Castilla y Leon",
    "Valladolid": "Castilla y Leon", "Zamora": "Castilla y Leon",
    "A Coruna": "Galicia", "La Coruna": "Galicia", "Lugo": "Galicia",
    "Ourense": "Galicia", "Orense": "Galicia", "Pontevedra": "Galicia",
    "Murcia": "Murcia",
    "Huesca": "Aragon", "Teruel": "Aragon", "Zaragoza": "Aragon",
    "Asturias": "Asturias",
    "Badajoz": "Extremadura", "Caceres": "Extremadura",
    "Baleares": "Baleares", "Illes Balears": "Baleares", "Islas Baleares": "Baleares",
    "Cantabria": "Cantabria",
    "Albacete": "Castilla-La Mancha", "Ciudad Real": "Castilla-La Mancha",
    "Cuenca": "Castilla-La Mancha", "Guadalajara": "Castilla-La Mancha",
    "Toledo": "Castilla-La Mancha",
    "Alicante": "Comunidad Valenciana", "Castellon": "Comunidad Valenciana",
    "Valencia": "Comunidad Valenciana",
    "Barcelona": "Cataluna", "Girona": "Cataluna", "Gerona": "Cataluna",
    "Lleida": "Cataluna", "Lerida": "Cataluna", "Tarragona": "Cataluna",
}


# --- Cliente HTTP mínimo -----------------------------------------------------


class Api:
    def __init__(self, base: str, usuario: str | None, password: str | None, simular: bool):
        self.base = base.rstrip("/")
        self.simular = simular
        self.cabeceras = {"Content-Type": "application/json"}
        if usuario and password:
            cred = base64.b64encode(f"{usuario}:{password}".encode()).decode()
            self.cabeceras["Authorization"] = f"Basic {cred}"

    def _peticion(self, metodo: str, ruta: str, cuerpo: dict | None = None):
        url = f"{self.base}{ruta}"
        if self.simular:
            print(f"  [simulado] {metodo} {ruta} {json.dumps(cuerpo, ensure_ascii=False) if cuerpo else ''}")
            return None
        datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
        req = urllib.request.Request(url, data=datos, headers=self.cabeceras, method=metodo)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                texto = r.read().decode()
                return json.loads(texto) if texto else None
        except urllib.error.HTTPError as e:
            detalle = e.read().decode()[:300]
            raise SystemExit(f"ERROR {e.code} en {metodo} {ruta}: {detalle}")
        except urllib.error.URLError as e:
            raise SystemExit(
                f"No se pudo conectar a {url}: {e.reason}\n"
                "¿Está levantado el backend? En el VPS la API va por nginx "
                "(--url http://localhost/api), no por el puerto 8000."
            )

    def put(self, ruta: str, cuerpo: dict):
        return self._peticion("PUT", ruta, cuerpo)

    def get(self, ruta: str):
        return self._peticion("GET", ruta)


# --- Carga -------------------------------------------------------------------


def _gasto(api: Api, *, pais, region, concepto, tipo, valor, moneda, fuente,
           exento=False) -> None:
    api.put("/config/gastos-adquisicion", {
        "pais": pais, "region": region, "concepto": concepto, "tipo": tipo,
        "valor": valor, "moneda": moneda, "fuente": fuente,
        "exento_confotur": exento,
    })


def cargar(api: Api) -> None:
    print("España — ITP por comunidad autónoma (19 filas)")
    for region, tipo_itp in ITP_ES:
        _gasto(api, pais="ES", region=region, concepto="ITP", tipo="PORCENTAJE",
               valor=tipo_itp, moneda="EUR", fuente=FUENTE_ITP_ES)

    print("España — gastos fijos comunes (region vacía, aplican a todas)")
    for concepto, importe in FIJOS_ES:
        _gasto(api, pais="ES", region="", concepto=concepto, tipo="FIJO",
               valor=importe, moneda="EUR", fuente=FUENTE_FIJOS_ES)

    print(f"España — mapa provincia → comunidad ({len(PROVINCIAS_ES)} provincias)")
    for provincia, region in PROVINCIAS_ES.items():
        api.put("/config/regiones-fiscales", {
            "pais": "ES", "provincia": provincia, "region": region,
            "fuente": FUENTE_REGIONES,
        })

    print("República Dominicana — gastos de adquisición (con marca CONFOTUR)")
    for concepto, tipo, valor, exento, fuente in GASTOS_DO:
        _gasto(api, pais="DO", region="", concepto=concepto, tipo=tipo,
               valor=valor, moneda="USD", fuente=fuente, exento=exento)

    print("República Dominicana — tipo de interés hipotecario 11,5 %")
    # NOTA: 11,5% es la financiación en DOP. En USD la tasa habitual es 7-8%, pero
    # `config_mercado_pais` guarda UN tipo por país, no uno por moneda: el modelo
    # NO puede diferenciar por divisa hoy. Se carga el de DOP por ser el que
    # aplica a la financiación local. Un inmueble en USD sale con la cuota
    # sobreestimada, y por tanto con el ROI a la baja (error conservador).
    api.put("/config/mercado-pais/DO", {
        "tipo_interes_anual": "0.115",
        "tipo_interes_estado": "PROVISIONAL",
    })

    print("Venezuela — gasto de cierre agregado 10 %")
    for concepto, tipo, valor, exento, fuente in GASTOS_VE:
        _gasto(api, pais="VE", region="", concepto=concepto, tipo=tipo,
               valor=valor, moneda="USD", fuente=fuente, exento=exento)

    print("\nHecho. NO se han cargado (a propósito): costes de reforma, "
          "benchmarks de zona ni catálogos de riesgo de DO/VE.")


def purgar(api: Api) -> None:
    """Revierte lo que carga este script, y solo eso.

    Se borra poniendo el valor a NULL en vez de eliminando la fila: así la UI
    sigue mostrando el concepto como hueco pendiente en lugar de hacerlo
    desaparecer sin dejar rastro de que hacía falta.
    """
    print("Purgando ITP de España (valor → NULL)")
    for region, _ in ITP_ES:
        _gasto(api, pais="ES", region=region, concepto="ITP", tipo="PORCENTAJE",
               valor=None, moneda="EUR", fuente="purgado por cargar_config_mercado.py")

    print("Purgando gastos fijos de España")
    for concepto, _ in FIJOS_ES:
        _gasto(api, pais="ES", region="", concepto=concepto, tipo="FIJO",
               valor=None, moneda="EUR", fuente="purgado por cargar_config_mercado.py")

    print("Purgando gastos de RD")
    for concepto, tipo, _, exento, _f in GASTOS_DO:
        _gasto(api, pais="DO", region="", concepto=concepto, tipo=tipo, valor=None,
               moneda="USD", fuente="purgado por cargar_config_mercado.py", exento=exento)

    print("Purgando gastos de VE")
    for concepto, tipo, _, exento, _f in GASTOS_VE:
        _gasto(api, pais="VE", region="", concepto=concepto, tipo=tipo, valor=None,
               moneda="USD", fuente="purgado por cargar_config_mercado.py", exento=exento)

    print("Purgando tipo de interés de RD")
    api.put("/config/mercado-pais/DO", {
        "tipo_interes_anual": None, "tipo_interes_estado": "PENDIENTE",
    })

    print("\nEl mapa provincia → comunidad NO se purga: no es un dato de mercado "
          "opinable, es división administrativa. Bórralo a mano si de verdad hace falta.")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default="http://localhost:8000/api",
                   help="Base de la API (VPS: http://localhost/api)")
    p.add_argument("--usuario", default=None, help="Usuario de la auth básica (VPS)")
    p.add_argument("--password", default=None, help="Contraseña de la auth básica (VPS)")
    p.add_argument("--purgar", action="store_true", help="Revierte lo cargado")
    p.add_argument("--simular", action="store_true", help="Enseña qué haría, sin tocar nada")
    a = p.parse_args()

    api = Api(a.url, a.usuario, a.password, a.simular)
    if not a.simular:
        api.get("/salud")  # falla pronto y claro si la API no responde
    print(f"{'PURGANDO' if a.purgar else 'CARGANDO'} configuración en {a.url}\n")
    (purgar if a.purgar else cargar)(api)


if __name__ == "__main__":
    sys.exit(main())
