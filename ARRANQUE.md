# ARRANQUE — de cero a primer inmueble rankeado

Documento único de puesta en marcha. Si no te acuerdas de nada, empieza aquí y ve en
orden. Para el *por qué* de cada decisión, `docs/DECISIONES.md`.

---

## 0. Qué es esto, en 30 segundos

Pipeline que descubre anuncios inmobiliarios, los normaliza, los juzga
cualitativamente con Claude, calcula sus métricas financieras en Python y los rankea
por perfil de inversor. Multi-país (ES / DO / VE) y multi-divisa.

Tres reglas que explican casi todo el comportamiento raro que te vas a encontrar:

1. **Python calcula, Claude interpreta.** Ningún número financiero sale del LLM.
2. **Cero criterios de negocio en el código.** Pesos, umbrales, costes y saturaciones
   viven en BD y se editan desde la UI.
3. **No se inventan datos.** Falta un dato → el inmueble sale `NO_CALCULABLE` y el
   sistema dice qué falta. **Ningún país arranca hasta cargar sus datos, España
   incluida.** Si al arrancar no ves nada en el ranking, casi seguro es esto y es el
   comportamiento correcto, no un fallo.

---

## 1. Arranque (comandos exactos, en orden)

Requisitos: Docker Desktop, Python 3.11+ (probado en 3.12.10), Node 18+ (probado en v24).

```bash
# 1. Base de datos (Postgres 16 en el puerto 5455)
docker compose up -d

# 2. Entorno Python
python -m venv .venv
#   PowerShell:  .venv\Scripts\Activate.ps1
#   bash/macOS:  source .venv/bin/activate
pip install -r requirements.txt

# 3. Configuración (ver §2; en local puedes saltártelo salvo la API key)
cp .env.example .env
#   PowerShell:  Copy-Item .env.example .env

# 4. Migraciones + seeds (idempotente: reejecutar no rompe nada)
python scripts/aplicar_migraciones.py

# 5. API  ->  http://localhost:8000  (Swagger en /docs)
python -m uvicorn backend.main:app --reload --port 8000

# 6. Frontend  ->  http://localhost:5173   (en otra terminal)
cd frontend && npm install && npm run dev

# 7. Worker de cron (OPCIONAL, solo si usas búsquedas programadas)
python -m backend.worker.worker
```

Comprobación de que está vivo:

```bash
curl http://localhost:8000/api/salud
# {"estado":"ok","base_datos":true,"openclaw":{"modo":"manual","disponible":true}}
```

Si `base_datos` no es `true`, el problema es el contenedor, no la app → §7.

---

## 2. Variables de `.env`, en orden

| Variable | ¿Obligatoria? | Qué pasa si falta |
|---|---|---|
| `DATABASE_URL` | En local **no** | Hay un default que ya coincide con `docker-compose` (`postgresql://inmo:inmo@localhost:5455/inmobiliaria`). En Supabase/producción sí es obligatoria. |
| `ANTHROPIC_API_KEY` | **Sí, para rankear** | El análisis falla → el inmueble queda `ANALISIS_FALLIDO` y **puntúa igual, pero sin juicio cualitativo**: varios componentes se quedan sin datos, se redistribuye su peso y el score sale `PARCIAL`/`NO_CALCULABLE`. Ver la trampa de §5. |
| `ANTHROPIC_MODEL` | No | Default `claude-sonnet-5`. |
| `ANTHROPIC_MAX_TOKENS` | No | Default 4096. |
| `OPENCLAW_MODE` | No | Default `manual` (copias el prompt y pegas el JSON). `http` = el cliente llama al VPS solo. |
| `OPENCLAW_BASE_URL` / `OPENCLAW_API_KEY` | Solo si `OPENCLAW_MODE=http` | Sin VPS no hace falta nada. |
| `OPENCLAW_LIMITE_ANUNCIOS` | No | Default 50. Controla coste y tiempo por job. |
| `WORKER_*`, `API_*`, `LOG_NIVEL`, `ENTORNO` | No | Tienen defaults sensatos. |
| `PROPIETARIO_POR_DEFECTO` | No | Mono-usuario. Solo importa el día que actives multi-tenant. |

Regla: `.env` **nunca** se sube (está en `.gitignore`).

---

## 3. De vacío a primer inmueble rankeado

### 3.1 Cargar la configuración de mercado — **la pantalla que manda**

Abre **"Estado por país"** (`http://localhost:5173/estado`). Es tu lista de tareas: te
dice exactamente qué falta para que cada país sea operativo. Trabaja contra esa pantalla
hasta que el país que te interesa salga **Operativo**.

Lo que hay que cargar por país (en **"Configuración"**, `/mercado`):

| Dato | Qué es | Sin él |
|---|---|---|
| **Costes de reforma** (€/m²) | Uno por nivel: `COSMETICA`, `MEDIA`, `INTEGRAL` | El coste de reforma no se calcula → score `PARCIAL` |
| **Gastos de adquisición** | ITP, notaría, registro… (`PORCENTAJE` o `FIJO`) | `PARCIAL` |
| **Benchmarks de zona** | €/m² venta y €/m²/**mes** alquiler por ciudad (y barrio) | Sin ellos no hay `descuento_mercado` ni renta → lo más limitante |
| **Tipos de cambio** | Solo si el país no opera en la moneda de referencia (EUR) | `NO_CALCULABLE` nombrando el par que falta. **Carga manual, sin feeds** |
| **Riesgos del país** | Qué códigos del catálogo son eliminatorios y cuánto penalizan los demás | Ver el aviso de §3.2 — esto es serio |

**Ojo con la UI:** la edición *inline* de costes funciona, pero **dar de alta filas nuevas
de gastos y benchmarks desde la pantalla está incompleto**. Para esas, usa la API:

```bash
# Gasto de adquisición
curl -X PUT http://localhost:8000/api/config/gastos-adquisicion \
  -H "Content-Type: application/json" \
  -d '{"pais":"ES","region":"","concepto":"ITP","tipo":"PORCENTAJE","valor":0.10,"moneda":"EUR","fuente":"Agencia Tributaria"}'

# Benchmark de zona (alquiler es €/m² AL MES)
curl -X PUT http://localhost:8000/api/config/benchmarks \
  -H "Content-Type: application/json" \
  -d '{"pais":"ES","ciudad":"Madrid","barrio":null,"moneda":"EUR","precio_m2_venta_medio":4200,"precio_m2_alquiler_medio":16.5,"rentabilidad_bruta_media_zona":0.047,"fuente":"idealista","fecha_dato":"2026-01-31"}'

# Coste de reforma
curl -X PUT http://localhost:8000/api/config/costes-reforma \
  -H "Content-Type: application/json" \
  -d '{"pais":"ES","nivel_reforma":"MEDIA","coste_m2":800,"moneda":"EUR","fuente":"presupuestos propios"}'

# Tipo de cambio (manual)
curl -X PUT http://localhost:8000/api/config/tipos-cambio \
  -H "Content-Type: application/json" \
  -d '{"moneda_origen":"USD","moneda_destino":"EUR","tasa":0.92,"fuente":"banco central","fecha":"2026-01-31"}'
```

Rellena siempre `fuente`: es lo que te va a decir dentro de tres meses si un número es
de fiar o te lo trajo el viento.

### 3.2 Riesgos por país — el que muerde

`riesgos_pais` está poblado **solo para ES** (9 códigos). **DO y VE están vacíos.**

Mientras un país esté vacío, **ninguna señal de riesgo cruza: ni los eliminatorios**. Un
piso con `OKUPAS` en RD **entraría al ranking sin descartar ni penalizar**. Es config que
falta, no un bug, pero el sistema no te deja ignorarlo:

- "Estado por país" marca ese país como **"Calibración incompleta"** con aviso explícito.
- Cualquier score cuyas señales acabaron ignoradas **nunca sale `COMPLETO`**: baja a
  `PARCIAL` y el ranking lo marca con **`SEÑAL IGNORADA`**.

Por qué importa tanto: sin catálogo, `riesgo_activo` se queda sin penalizaciones y eso
normaliza al **máximo** ("sin riesgo alguno" = 100 puntos). O sea, **el fallo empuja el
score al alza**, justo en la dirección peligrosa para quien decide comprar.

Códigos del catálogo (`catalogo_riesgos`, 18) disponibles para asignar:

- **Riesgo:** `ALQUILADO_RENTA_ANTIGUA`, `CARGAS`, `DERRIBO`, `ESTADO_A_REFORMAR`,
  `ESTADO_RUINA`, `LITIGIO_JUDICIAL`, `OCUPACION_INFORMAL`, `OKUPAS`, `PROINDIVISO`,
  `RIESGO_EXPROPIACION`, `SIN_CEDULA`, `SIN_TITULO_CLARO`, `SUBASTA`
- **Oportunidad:** `HERENCIA`, `PARTICULAR_SIN_AGENCIA`, `PRECIO_REBAJADO`,
  `REFORMABLE_CON_MARGEN`, `VENTA_URGENTE`
- **Sin asignar a ningún país** (candidatos pensados para DO/VE):
  `LITIGIO_JUDICIAL`, `OCUPACION_INFORMAL`, `RIESGO_EXPROPIACION`, `SIN_TITULO_CLARO`

Asignar un riesgo a un país:

```bash
# Eliminatorio (descarte duro): penalizacion se ignora
curl -X PUT http://localhost:8000/api/config/riesgos-pais/DO \
  -H "Content-Type: application/json" \
  -d '{"codigo":"OKUPAS","es_eliminatorio":true}'

# Ponderable: resta puntos
curl -X PUT http://localhost:8000/api/config/riesgos-pais/DO \
  -H "Content-Type: application/json" \
  -d '{"codigo":"SIN_TITULO_CLARO","es_eliminatorio":false,"penalizacion":-40}'
```

Referencia: el mapa de ES aprobado es `CARGAS -50, PROINDIVISO -40, ESTADO_RUINA -40,
ALQUILADO_RENTA_ANTIGUA -35, SUBASTA -30, SIN_CEDULA -25, ESTADO_A_REFORMAR -10`, y
eliminatorios `OKUPAS`, `DERRIBO`.

### 3.3 Portal, búsqueda y extracción

1. **"Portales"** (`/portales`): da de alta el portal y una búsqueda (ciudad,
   presupuesto, tipo). El cron es opcional; sin él, es manual.
2. Pulsa **"Ejecutar ahora"** → crea un job y genera el prompt.
3. **"Monitor"** (`/jobs`) en modo `manual`:
   - Abre el job → **Copiar** el prompt.
   - Pégalo en tu OpenClaw del VPS (system prompt en `docs/PROMPT_PARA_OPENCLAW.md`).
   - Pega el JSON de vuelta en **"Pegar JSON de vuelta"** → **Ingestar resultado**.
4. La ingesta valida **anuncio a anuncio**: los válidos entran, los inválidos van a
   **cuarentena** (visible en el mismo monitor) y el job queda `PARCIAL`. Eso es correcto:
   un anuncio malo no tumba el lote.
5. Automáticamente: normalización → análisis (Claude) → métricas → scores.
6. **"Ranking"** (`/`): ahí está el resultado.

### 3.4 Parámetros PROVISIONALES

`riesgo_pais`, `roi_neto_minimo`, saturaciones y `descuento_minimo_interes` arrancan
marcados `PROVISIONAL`. Cualquier score que los use lleva el badge **`PROV`** en el
ranking. Cuando valides un valor con fuente real, cámbialo a `VALIDADO`
(`PUT /api/config/mercado-pais/{pais}` o `/umbrales/{perfil}/{pais}`).

---

## 4. Antes del primer lote: prueba de humo de Claude

**Esto es lo primero que se va a romper.** La llamada real a Claude nunca se ha
ejecutado (se construyó sin API key). Antes de gastar un lote entero:

```bash
# PowerShell
$env:ANTHROPIC_API_KEY="sk-ant-..."; python scripts/probar_analista.py
# bash
ANTHROPIC_API_KEY="sk-ant-..." python scripts/probar_analista.py
```

Sobre un solo anuncio ficticio: imprime el esquema exacto que se le fuerza a Claude,
llama a la API, enseña la respuesta cruda, la parsea con Pydantic y **cruza las señales
contra el catálogo**. Falla ruidosamente (salida ≠ 0) con el motivo concreto.

Qué puede decirte:
- **La API rechaza el esquema** → structured outputs no traga algo (`$defs`, enums,
  `additionalProperties`). Es el fallo que este script existe para cazar.
- **El JSON no valida** → campo extra (`extra="forbid"`), enum fuera de rango, o un
  número donde debía ir una categoría.
- **`FUERA DE CATALOGO: [...]`** → Claude inventa códigos, o te falta ese código en el
  catálogo del país. Ninguna de las dos se ve sin la key puesta.

---

## 5. Trampa importante: los fallos del analista se ven todos iguales

El bucle de reintentos de `analista_cualitativo.analizar()` traga **cualquier**
excepción y, tras 2 reintentos, marca `ANALISIS_FALLIDO`. Consecuencia: *"falta la API
key"*, *"el paquete `anthropic` no está instalado"* (el import es perezoso) y *"el
esquema no le gusta a la API"* se ven **exactamente igual** desde la UI: un inmueble sin
análisis.

Si ves `ANALISIS_FALLIDO` en masa, **no depures desde la UI**: corre
`scripts/probar_analista.py`, que sí te dice la causa real.

---

## 6. Ver la UI con contenido sin scrapear nada

Para revisar el diseño o enseñarlo sin montar OpenClaw:

```bash
python scripts/demo_datos_visuales.py            # siembra
python scripts/demo_datos_visuales.py --purgar   # borra TODO lo que sembró
```

Las **cifras no son inventadas**: las calculan los motores reales. Lo ficticio son los
*inputs* (anuncios, benchmarks, gastos), marcados con `fuente='DEMO'` y portal
`DEMO Visual`.

> **PURGA SIEMPRE ANTES DE CARGAR DATOS REALES.** Con la demo puesta, "Estado por país"
> marca **ES como Operativo** con benchmarks de mentira. Es exactamente el fallo
> silencioso que este sistema intenta evitar.

Capturas de referencia de la UI en `docs/capturas/`.

---

## 7. Trampas de esta máquina

- **Docker Desktop es inestable aquí.** Se ha caído varias veces. Si `/api/salud` da
  `base_datos:false` o el puerto 5455 no escucha:
  ```powershell
  Start-Process 'C:\Program Files\Docker\Docker\Docker Desktop.exe'   # ~35 s al daemon
  docker compose up -d
  ```
  El volumen `datos_postgres` persiste: no pierdes ni el esquema ni los datos.
- **Puertos 5432 y 5433 ocupados** por otro stack tuyo (`valencia-*`). Por eso este
  proyecto usa **5455**.
- **`anthropic` puede no estar instalado** en el intérprete global (el import es
  perezoso, así que no falla al arrancar): `pip install -r requirements.txt`.
- **Git no tiene identidad configurada** y el repo **no tiene ningún commit**; todo está
  en el índice sin commitear. Antes del primer commit:
  `git config user.name "..."` y `git config user.email "..."`.
- **Las capturas del navegador integrado dan timeout** (renderer pesado con recharts).
  Chrome headless sí funciona:
  ```bash
  chrome --headless=new --disable-gpu --virtual-time-budget=8000 \
         --window-size=1440,900 --screenshot=out.png http://localhost:5173/
  ```

---

## 8. Frentes abiertos y limitaciones conocidas

Ordenados por lo que te va a morder antes.

1. **La llamada real a Claude nunca se ha ejecutado.** Único frente realmente abierto.
   Mitigación: §4.
2. **`riesgos_pais` vacío en DO y VE.** Hasta que los cargues, ninguna señal de riesgo
   aplica en tus dos mercados clave. Está blindado y señalizado (§3.2), pero sigue siendo
   config que falta.
3. **`calidad_zona` y `margen_reforma` son proxies MVP.** `calidad_zona` = rentabilidad
   bruta media de la zona; `margen_reforma` = el descuento si el inmueble es reformable.
   Son débiles hasta tener serie temporal por zona y un modelo real de margen de obra.
   **Pesan 25% + 20% en `PLUSVALIA_LARGO_PLAZO`**: ese perfil es más flojo que el de
   cashflow, tenlo presente al leer su ranking.
4. **Dedup cross-portal es heurística tosca**: misma ciudad + precio ±5% + m² ±5%. Solo
   **marca** (`DUP` en el ranking), nunca fusiona. Dará falsos positivos y negativos.
5. **Señales ignoradas: lista plana.** `senales_no_reconocidas` no distingue si el código
   ignorado era de riesgo o de oportunidad, así que se marca `PARCIAL` en ambos casos.
   Conservador a propósito (nunca deja algo más limpio de lo que es), pero un código de
   oportunidad ignorado también degrada el estado.
6. **Métricas canónicas con los supuestos del perfil predeterminado.** La ficha muestra
   la financiación de `CASHFLOW_CORTO_PLAZO`; el ROI exacto de cada perfil vive en el
   `desglose` de su score. Es decisión de modelo, no bug.
7. **Modo `http` de OpenClaw sin ejercitar** (nunca hubo VPS). El modo `manual` sí
   funciona de punta a punta.
8. **RLS permisivo + CORS `*`.** Mono-usuario auto-hospedado. **No lo expongas a internet
   tal cual.** El esquema ya está preparado para multi-tenant (`propietario_id`): migrar
   es cambiar la política, sin tocar tablas.
9. **Frontend**: alta de filas nuevas de gastos/benchmarks incompleta (usa la API, §3.1);
   los sliders de pesos avisan si no suman 100% pero no lo bloquean.

**Ya resuelto, para que no lo dudes dentro de tres meses:**

- **FX dentro del cálculo.** El motor financiero normaliza **todos** los inputs
  monetarios (precio, coste de reforma, gastos fijos, benchmarks) a la moneda de cálculo
  **antes de operar**; las tasas entran como datos desde `tipos_cambio`. Si falta una
  tasa → `NO_CALCULABLE` **nombrando el par** (p. ej. `tipo_cambio[DOP->USD]`), jamás se
  inventa. España (todo EUR) no se ve afectada. Motor en `motor-financiero-1.1.0`,
  verificado end-to-end con USD + benchmark en DOP.
- **Señales fuera de catálogo.** Validadas contra el catálogo del país; las desconocidas
  van a `senales_no_reconocidas`, visibles en ficha y monitor, y degradan el score a
  `PARCIAL`. Ya no se ignoran en silencio.

---

## 9. Mapa rápido

| Quiero… | Está en |
|---|---|
| Saber por qué se decidió algo | `docs/DECISIONES.md` |
| Cambiar una fórmula financiera | `backend/dominio/motor_financiero.py` (puro) |
| Cambiar cómo se combinan los componentes | `backend/dominio/motor_scoring.py` (puro) |
| Cambiar un peso/umbral/coste | **La UI o la BD, nunca el código** (hay un test que te para) |
| El prompt de OpenClaw para el VPS | `docs/PROMPT_PARA_OPENCLAW.md` |
| Envolver OpenClaw en HTTP | `scripts/adaptador_openclaw_vps.py` (solo falta `ejecutar_openclaw()`) |
| Endpoints | `http://localhost:8000/docs` |

**Tests:** `python -m pytest` → **49 passed**. Dos de ellos son barreras, no
comprobaciones: `test_anti_hardcode.py` falla si metes un peso en `backend/dominio/`, y
`test_analista_sin_numeros.py` falla si el esquema de Claude gana un campo numérico. Si
alguno se pone rojo, no lo "arregles" — has cruzado uno de los dos principios.
