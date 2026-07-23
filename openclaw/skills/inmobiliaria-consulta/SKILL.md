---
name: inmobiliaria-consulta
description: Consulta de solo lectura del sistema de sourcing inmobiliario (ES/DO/VE). Úsala cuando pregunten por el ranking de inmuebles, la ficha de un inmueble, cuántos inmuebles hay por país, qué configuración le falta a un país para ser operativo, o el estado de los jobs de extracción.
metadata:
  openclaw:
    requires:
      bins:
        - curl
        - python3
      env:
        - INMO_API_BASE
        - INMO_CONSULTA_USUARIO
        - INMO_CONSULTA_PASSWORD
---

# Consulta del sistema de sourcing inmobiliario

Contesta preguntas sobre un sistema que descubre anuncios inmobiliarios, los
puntúa y los ordena por perfil de inversor. Los datos son reales: **siempre** se
obtienen llamando al script, nunca de memoria ni por deducción.

## Regla número uno: solo lectura

Esta skill **solo consulta**. No puedes crear búsquedas, borrar inmuebles,
cambiar configuración, lanzar jobs ni recalcular nada desde el chat.

Si te piden una de esas cosas, explica que la consulta por chat es de solo
lectura y que hay que hacerlo desde la aplicación web. No busques rodeos: la API
de lectura rechaza cualquier método que no sea GET, así que un intento fallaría
igualmente con un 403.

## Cómo consultar

Ejecuta `consultar.sh` (está junto a este fichero) con el subcomando que toque.
Devuelve texto ya legible; **tú lo rediges en lenguaje natural.**

| Pregunta del usuario | Comando |
|---|---|
| "top 5 del ranking de España" | `./consultar.sh ranking ES --limite 5` |
| "los mejores en general" | `./consultar.sh ranking global --limite 10` |
| "el ranking por plusvalía" | `./consultar.sh ranking --perfil plusvalia --limite 10` |
| "el ranking sin penalizar por riesgo país" | `./consultar.sh ranking --bruto` |
| "qué perfiles hay" | `./consultar.sh perfiles` |
| "cuéntame ese piso" / "detalles del id X" | `./consultar.sh inmueble <uuid>` |
| "ha bajado de precio?" | `./consultar.sh historico <uuid>` |
| "cuántos inmuebles hay por país" | `./consultar.sh inventario` |
| "qué me falta para que Venezuela sea operativo" | `./consultar.sh estado-pais VE` |
| "cómo está la configuración" | `./consultar.sh estado-pais` |
| "hay algún job fallido y por qué" | `./consultar.sh jobs` |
| "qué señales se están ignorando" | `./consultar.sh senales-fuera-catalogo` |
| "está viva la API?" | `./consultar.sh salud` |

Para **"resúmeme los pisos con score mayor a 60"** no hay filtro por score en la
API: pide `ranking` con un límite holgado (`--limite 50`) y filtra tú los que
superen el umbral al redactar.

Si el usuario menciona un inmueble del que ya has dado el `id` en la conversación,
reutilízalo con `inmueble <uuid>` en vez de volver a pedir el ranking entero.

## Cómo responder

Escribe como se lo contarías a la persona que va a decidir la compra.

- **Nada de JSON crudo ni volcados de texto del script en el chat.** Redacta.
- Cifras: precio con su moneda, superficie en m², score con un decimal.
- Listas cortas: para un top, una línea por inmueble con score, título, ciudad y
  precio. Los detalles solo si los piden.
- No inventes datos que el script no haya devuelto. Si un campo viene vacío, dilo.

## Lo que SIEMPRE debes trasladar

El sistema está diseñado para no engañar a quien decide. Si el script devuelve
un `AVISO`, tiene que llegar a la respuesta:

- **Señales fuera de catálogo** → el score puede estar **infra-penalizado**, es
  decir, mejor de lo que la realidad soporta. Nunca presentes ese inmueble como
  una oportunidad limpia sin mencionarlo.
- **Zona turística** → el score de cashflow no aplica bien ahí (la inversión es
  de plusvalía o corta estancia). Un score bajo no significa mala inversión.
- **Parámetros provisionales** → la configuración de mercado aún no está validada,
  así que el número es orientativo.
- **Calidad del dato** (`COMPLETO` / `PARCIAL` / `NO_CALCULABLE`) → menciónala
  siempre que des un score. Un `PARCIAL` significa que faltaban componentes y su
  peso se repartió entre los demás.
- **País no operativo** → sus scores no son comparables con los de un país
  calibrado.

## Contexto que ayuda a redactar bien

- Hay dos perfiles de inversor: **CASHFLOW_CORTO_PLAZO** (el predeterminado, pesa
  sobre todo la rentabilidad neta) y **PLUSVALIA_LARGO_PLAZO** (pesa el descuento
  de mercado y la calidad de zona). El mismo inmueble puntúa distinto en cada uno.
- El score va de 0 a 100. **Un score ≥75 es excepcional y raro**: el trabajo del
  sistema es escanear mucho para encontrar los pocos que lo superan. No presentes
  un 45 como decepcionante ni un 80 como garantía.
- `score_total = score_bruto × (1 − riesgo_país)`. El bruto sirve para ver si una
  calibración de riesgo país está matando un mercado bueno.
- Países: ES (España), DO (República Dominicana), VE (Venezuela).

## Si algo falla

- **401** → las credenciales de solo lectura no son correctas o no están puestas.
- **403** → intentaste algo que no es GET. Es correcto que falle: recuérdalo y no
  insistas.
- **502** → el backend está caído; el resto del sistema puede seguir en pie.
- Script no encontrado o falta `curl`/`python3` → dilo tal cual, no simules datos.

Ante cualquier fallo, **di que no has podido consultar**. Nunca respondas con
datos aproximados o recordados de una consulta anterior como si fueran actuales.
