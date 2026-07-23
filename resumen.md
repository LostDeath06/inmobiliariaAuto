# resumen.md — SaaS de Sourcing y Análisis de Inversión Inmobiliaria

> **Qué es este documento.** El estado real del sistema y, sobre todo, **por qué** está
> construido así. Si vuelves dentro de tres meses sin recordar nada, esto debería
> bastarte para retomarlo sin repetir errores ya cometidos.
> Documentos hermanos: `ARRANQUE.md` (levantarlo en Windows), `DESPLIEGUE.md` (VPS),
> `docs/DECISIONES.md` (registro formal de decisiones).

---

## 0. Estado global

Producto **greenfield**, construido de la Fase 0 a la 9 y **desplegado 24/7**.

- **Producción:** https://inmobiliariaauto.com (VPS Hostinger + Cloudflare Tunnel, tras contraseña)
- **Local:** UI `localhost:5173` · API `localhost:8000/docs` · Postgres `5455`
- **Tests:** `49 passed`
- **Inventario:** 32 inmuebles reales (ES 16 · DO 16 · VE 0), los 32 analizados por Claude
- **Frente abierto único:** OpenClaw — código completo y desplegable, sin ejecutar aún
  contra el agente real

**Qué hace el sistema, en una frase:** descubre anuncios inmobiliarios, los normaliza,
los juzga cualitativamente con Claude, calcula sus métricas financieras en Python y los
ordena por perfil de inversor — diciendo siempre en qué se apoya y qué le falta.

---

## 1. Cómo trabajamos

- Construir en silencio, sin narrar progreso ni pedir confirmación por fase.
- Interrumpir solo por (1) una **decisión** de negocio/alcance, o (2) un **dato** que falta.
- **Honestidad sobre complacencia:** señalar lo que no funciona, aunque no se pregunte.

Esta última regla no es decorativa: ha cambiado el producto varias veces (§8). El caso
más caro fue descubrir que los scores que se veían "bien" en realidad no medían nada.

---

## 2. Los tres principios inviolables

### Principio 1 — Determinismo financiero: Python calcula, Claude interpreta

Ningún número financiero sale de un LLM. Todo cálculo vive en
`backend/dominio/motor_financiero.py`, **función pura**: sin I/O, sin red, sin fecha del
sistema. Claude solo devuelve enums, booleanos, categorías y texto corto.

**Por qué:** un LLM que "estima" una rentabilidad produce un número plausible e
irreproducible. Si el motor es puro, el mismo inmueble da siempre el mismo resultado y
se puede auditar cifra a cifra.

**Cómo se protege:** `tests/servicios/test_analista_sin_numeros.py` recorre el esquema de
salida de Claude y falla si aparece cualquier tipo `integer`/`number`. Es una barrera, no
una comprobación: si se pone rojo, alguien cruzó el principio.

### Principio 2 — Cero criterios de negocio en el código

Ningún peso, umbral, coste o tipo de interés en un `.py`. Todo vive en base de datos y se
edita desde la UI.

**Por qué:** los criterios de inversión cambian y son del propietario, no del programador.
Si un peso está hardcodeado, cambiarlo exige un despliegue y el histórico deja de ser
comparable.

**Cómo se protege:** `tests/dominio/test_anti_hardcode.py` escanea literales numéricos a
nivel de módulo en `backend/dominio/` fuera de una allowlist `{0,1}`. Meter
`PESO_RENTABILIDAD = 0.40` hace fallar el test nombrando la variable.

### Principio 3 — Un fallo silencioso es peor que un fallo ruidoso

Añadido durante el trabajo de señales. Si el sistema no puede calcular algo bien, **lo
dice**: nunca presenta un número mejor de lo que la realidad soporta.

**Por qué:** un `NO_CALCULABLE` visible cuesta cinco minutos. Un score inflado que parece
bueno cuesta una inversión.

---

## 3. Cómo se calcula un score (lo que hay que entender para leer el ranking)

El score **no es un dato del inmueble**: lo calcula el motor a partir de la
**configuración de mercado del país**. Sin esa configuración, el número no significa nada.

### 3.1 Los siete componentes

| Componente | De dónde sale |
|---|---|
| `rentabilidad_neta` | ROI neto del motor financiero (necesita alquiler de zona, gastos, tipo de interés) |
| `descuento_mercado` | `1 − (precio_m2 / precio_m2_venta_medio de la zona)` |
| `calidad_zona` | Rentabilidad bruta media de la zona *(proxy MVP)* |
| `margen_reforma` | El descuento si el inmueble es reformable *(proxy MVP)* |
| `aptitud_alquiler` | Juicio de Claude: SI=1 · DUDOSO=0.5 · NO=0 |
| `riesgo_activo` | Suma de penalizaciones del catálogo de riesgos del país |
| `oportunidad_temporal` | Bajada de precio en el histórico + señal cualitativa |

Cada uno se normaliza 0–100 con su curva (`{min, max, dirección}`) tomada de
`config_mercado_pais`. **Un componente sin datos no vale 0: se excluye y su peso se
redistribuye** entre los calculables, y el score se marca `PARCIAL`.

Ese detalle explica casi todo el comportamiento raro: **si solo un componente es
calculable, ese componente se lleva el 100% del peso.**

### 3.2 Los dos perfiles (valores reales en BD)

| Componente | CASHFLOW_CORTO_PLAZO *(predeterminado)* | PLUSVALIA_LARGO_PLAZO |
|---|---|---|
| rentabilidad_neta | **0.40** | 0.10 |
| descuento_mercado | 0.15 | **0.25** |
| calidad_zona | 0.05 | **0.25** |
| margen_reforma | 0.05 | 0.20 |
| aptitud_alquiler | 0.15 | 0.05 |
| riesgo_activo | 0.10 | 0.10 |
| oportunidad_temporal | 0.10 | 0.05 |

Supuestos: ambos `ltv 0.70`, `vacancia 5%`, `gestión 8%`; plazo 25 años (cashflow) y 30
(plusvalía).

### 3.3 Riesgo país y descarte

`score_total = score_bruto × (1 − riesgo_pais)`. Se guardan **los dos**, y el ranking
tiene un interruptor "sin riesgo país" para ver el bruto — salvaguarda contra una
calibración que mate un mercado bueno.

Los riesgos **eliminatorios** (p. ej. `OKUPAS`) no se ponderan: descartan el inmueble
(`DESCARTADO_RIESGO`) y lo sacan del ranking.

### 3.4 Qué significa realmente un score alto

**Un score ≥75 es un chollo excepcional, y los chollos son raros por definición.** Ese es
el trabajo del sistema: escanear cientos de anuncios para encontrar los pocos que lo
superan. No es algo que se pueda "pedir a la carta": forzarlo exigiría inflar los
benchmarks, que es inventar datos.

Rangos reales hoy (32 inmuebles, config provisional):

| Perfil | Rango | `COMPLETO` |
|---|---|---|
| CASHFLOW_CORTO_PLAZO | 27.3 – 79.8 | 0 |
| PLUSVALIA_LARGO_PLAZO | 27.4 – 83.7 | 0 |

Ninguno sale `COMPLETO` porque la configuración de mercado es provisional y falta dato en
todos. **Eso es correcto**, no un fallo.

---

## 4. Señales fuera de catálogo y el sesgo al alza

Esta es la parte más sutil del sistema. Merece entenderse entera.

### 4.1 El problema

El catálogo de riesgos vive en BD y **varía por país**. `senales_riesgo` es `list[str]`
(no puede ser un enum: el catálogo es dato, no código). Así que un código que Claude
devolviera fuera de catálogo —inventado o mal escrito— pasaba la validación de Pydantic y
después **no cruzaba con nada**: ni descarte duro, ni penalización. Se ignoraba en
silencio. Un riesgo real podía quedar sin efecto sin que nadie lo viera.

### 4.2 La solución: `validar_senales()`

Función pura en `analista_cualitativo.py`, aplicada al procesar la salida de Claude:

- Código **dentro** de catálogo → se conserva en su lista y surte efecto.
- Código **fuera** de catálogo → se separa a **`senales_no_reconocidas`** (migración
  `0006`), visible en la ficha y en el Monitor. **Nunca se descarta en silencio.**
- `NINGUNA` es sentinela de "sin señal": ni se aplica ni se marca.

Un código ahí significa una de dos cosas, ambas accionables: o el modelo alucina, o falta
ese código en el catálogo de ese país.

### 4.3 El blindaje: el fallo empujaba al alza

Aquí está el matiz peligroso. Sin catálogo, `riesgo_activo` se queda **sin
penalizaciones**, y "cero penalizaciones" normaliza al **máximo** (100 puntos = "sin
riesgo alguno"). Es decir: **el fallo no era neutro, inflaba el score** — justo en la
dirección que perjudica a quien decide comprar.

Por eso `ajustar_por_senales_ignoradas()` (función pura): un score con señales ignoradas
**nunca puede presentarse como `COMPLETO`** — se degrada a `PARCIAL` y los códigos quedan
en el `desglose`. El ranking lo marca con `SEÑAL IGNORADA` y la ficha lo explica.

Aplica también a España, no solo a RD/VE: si Claude devuelve un código que el catálogo de
ES no contempla, la penalización sale 0 y el score salía `COMPLETO`. Ese fue el caso real
que lo destapó.

Estado del catálogo: **ES 9 riesgos (2 eliminatorios) · DO 6 (2 eliminatorios) · VE 0**.

---

## 5. Zonas turísticas (Cap Cana)

Cap Cana es **plusvalía y alquiler de corta estancia**, no cashflow de larga estancia
apalancado. Con este motor puntúa bajo **siempre**, y eso no significa que sea mala
inversión: significa que el perfil no encaja.

La migración `0007` prepara el terreno **sin inventar un motor nuevo**:

- `perfil_zona` en `benchmarks_zona`: `ESTANDAR` | `TURISTICA`
- Campos de corta estancia, a rellenar por el propietario:
  `adr_medio` (tarifa media por noche) · `ocupacion_media` (0–1) ·
  `gastos_gestion_corta_pct`

Mientras no haya esos datos, la **ficha avisa** y el **ranking marca `TURÍSTICA`**, para
que un 32 de Cap Cana no se lea igual que un 32 de Santo Domingo. Cuando se carguen ADR y
ocupación, el cálculo de corta estancia es el paso siguiente
(`renta_corta ≈ ADR × 365 × ocupación × (1 − gestión)`).

Zonas marcadas hoy: Cap Cana, Bávaro y Punta Cana (3).

---

## 6. Datos reales cargados y el mapa de portales

| País | Inmuebles | Portal | Notas |
|---|---|---|---|
| **ES** | 16 | fotocasa | Valencia, Madrid, Málaga, Sevilla |
| **DO** | 16 | encuentra24 | Santo Domingo + Punta Cana/Bávaro (turístico) |
| **VE** | 0 | — | **Sin fuente disponible** |

Los 32 tienen URL real verificada y análisis real de Claude (0 fallidos).

**Portales probados** (esto ahorra repetir el trabajo):

| Portal | Resultado |
|---|---|
| `encuentra24` (DO) | **Funciona** — devuelve ~15 anuncios con URL |
| `fotocasa` (ES) | **Funciona**, pero suelta ~1 anuncio por página (lento) |
| `idealista`, `pisos.com`, `habitaclia` (ES) | **Bloquean** (403/404) |
| `mercadolibre.com.ve`, `tuinmueble.com` (VE) | **Bloquean** (403) |

Los de VE están **registrados en BD como portales inactivos con su motivo**, y la pantalla
"Estado por país" muestra: *"Sin fuente de anuncios disponible — todos los portales
probados bloquean acceso automatizado"*. Así, dentro de tres meses, VE vacío se explica
solo en vez de parecer un fallo.

### 6.1 Configuración de mercado (PROVISIONAL — pendiente de validar)

| País | Tipo interés | LTV máx | Riesgo país | Sat. rentab. | Sat. descuento |
|---|---|---|---|---|---|
| ES | 3.5% *(validado)* | 0.80 | 0.00 | 0.07 | 0.30 |
| DO | 11.5% *(provisional)* | 0.70 | 0.12 | 0.12 | 0.35 |
| VE | — *(al contado)* | 0.00 | 0.25 | 0.15 | 0.40 |

21 benchmarks de zona cargados, todos con la fuente citada y marcados `VALIDAR`.

> **Aviso importante sobre estos benchmarks.** Los de **nivel ciudad son gruesos** y
> distorsionan: usar la media de Madrid (€4.300/m²) para un barrio barato como
> Carabanchel hace que el motor lea un 39% de descuento donde solo hay un barrio más
> económico. El "79.8" del loft de Carabanchel es **artefacto de granularidad, no un
> chollo**. Afinar a nivel barrio es el trabajo pendiente que más cambiaría el ranking.

---

## 7. Arquitectura y despliegue

### 7.1 Pipeline (8 pasos, cada uno idempotente)

```
configuración → job → OpenClaw → ingesta → juicio cualitativo → métricas → scoring → ranking
                                    │            │                 │          │
                              dedup +      Claude +          motor puro   motor puro
                             cuarentena  validar_senales                 + blindaje
```

Un fallo en un inmueble se marca y el pipeline sigue: nunca aborta el lote.

### 7.2 Despliegue en el VPS

```
Internet → :80 nginx  (auth básica + proxy /api)
                ├── frontend (build estático de React)
                └── backend (FastAPI)      ← sin puerto publicado
                        ├── postgres       ← solo 127.0.0.1
                        └── worker (APScheduler)
     migraciones = one-shot: corre, termina, y solo entonces arranca el backend
```

Decisiones y su porqué:

- **Un solo comando:** `docker compose --profile vps up -d --build`.
- **El perfil `vps` existe** para que en Windows `docker compose up -d` levante *solo*
  Postgres y siga valiendo `ARRANCAR.bat`, sin arrancar contenedores que chocan con el
  uvicorn/vite locales.
- **Worker en contenedor aparte**, no dentro de la API: aislamiento de fallos y, sobre
  todo, **sin ticks duplicados** el día que se escale la API (dos réplicas con scheduler
  dentro dispararían cada cron dos veces).
- **Migraciones como servicio one-shot** con `service_completed_successfully`: el backend
  no acepta tráfico hasta que el esquema está al día.
- **`restart: unless-stopped`** en todo: si el VPS reinicia, el sistema vuelve solo.
- **nginx resuelve el backend en caliente** (`resolver 127.0.0.11` + upstream en
  variable). Sin eso, nginx resolvía el nombre al arrancar y **moría en bucle** si
  arrancaba antes que el backend — que es justo lo que pasa en un reinicio del VPS,
  porque Docker **no respeta `depends_on`** al relanzar por política `restart`.

### 7.3 Seguridad

- Auth básica de nginx sobre **toda** la app (web, API y `/docs`).
- El contenedor del frontend **se niega a arrancar sin contraseña** (falla a propósito,
  para que el sistema no pueda quedar expuesto por descuido).
- Backend y Postgres **sin puertos publicados** a internet.
- **Lo que NO hay:** TLS extremo a extremo. Cloudflare Tunnel pone TLS de cara al
  exterior, pero dentro del túnel la auth viaja por HTTP.

### 7.4 Frontend

Sistema de diseño propio sobre Tailwind (tokens CSS + estrategia `dark`), estética de
terminal financiero: oscuro por defecto con opción claro, jerarquía por niveles de gris,
**un único acento frío**, todas las cifras en monoespaciada alineadas a la derecha, score
por tramos sobrio, gráficos con la paleta propia. Sin emojis.

**Responsive** (medido a 375px y 768px, no a ojo): ranking en **tarjetas por debajo de
1024px** (a 768px la tabla medía ~890px y obligaba a arrastrar de lado), navegación
hamburguesa, áreas táctiles ≥44px, inputs a 16px en móvil para evitar el zoom de iOS,
gráficos ajustados al ancho, cero desbordamiento horizontal.

---

## 8. Decisiones que cambiaron el producto (leer antes de repetir errores)

### 8.1 El espejismo de los scores

Antes de cargar la configuración de mercado, los scores iban de **38 a 77** y parecían
razonables. En realidad medían *"a Claude le gustó"*: el único componente calculable era
`aptitud_alquiler`, y por la redistribución de pesos se llevaba el 100%.

Al cargar datos reales de RD, cayeron a **27–55** y **ninguno llegaba a 75**. El motivo
es económico y no un bug: a los precios y la hipoteca real de RD (11.5%), esos pisos
rinden ~5% neto — por debajo del coste del préstamo, así que el cashflow apalancado sale
plano. Ejemplo real (San Isidro, el mejor del lote): 26% bajo mercado, flujo de caja
+$1.123/año, ROI 1.2% → score 30/41. Buen piso, no excepcional.

**La lección:** un score sin configuración de mercado detrás no es un score.

### 8.2 Cap Cana medido con la regla equivocada

Puntuaba bajo porque el perfil no encaja, no porque sea mala inversión. De ahí §5.

### 8.3 El bug latente de `.value`

`repositorios/analisis.py` hacía `[s.value for s in analisis.senales_riesgo]` sobre una
`list[str]`. La primera llamada real a Claude que devolviera una señal no vacía habría
reventado con `AttributeError`. Nunca se había disparado porque Claude nunca se había
llamado de verdad.

### 8.4 `resumen_analista` con límite de 300 caracteres

Hizo fallar la **primera llamada real a Claude** (`string_too_long`). Todo lo demás
—structured outputs, enums, `$defs`— validó a la primera. Subido a 1000 con recorte
defensivo: fallar un análisis entero por un resumen largo era un mal modo de fallo.

### 8.5 Datos demo contaminando un score real *(detectado y corregido hoy)*

Un benchmark de Santo Domingo a nivel ciudad con `fuente: "demo"` (del 15 jul) **sobrevivió
a las purgas** porque el script filtraba `fuente='DEMO'` en mayúsculas. Un inmueble real
—Residencial Palmeras— se estaba puntuando contra datos inventados. Se eliminó (junto a un
benchmark mío mal ubicado, Bávaro bajo Santo Domingo) y se recalculó: ahora sale **61.60
`PARCIAL`**, que es el estado honesto porque esa zona no tiene benchmark.

**La lección:** las purgas por texto exacto son frágiles. Al cargar demo, comprobar
después con `lower(fuente) LIKE '%demo%'`.

---

## 9. OpenClaw — estado real

**Código completo, sin ejecutar contra el agente real.** Es el único frente abierto.

### 9.1 Cómo se invoca y por qué así

Se usa el **CLI**: `openclaw agent --message-file … --json --timeout …`, que la
documentación describe como *ejecución no interactiva hasta completar, con stdout separado
de stderr*.

Se descartó hablar el **WebSocket del Gateway** (`chat.send`) porque exigiría implementar
el handshake de protocolo v4, seguir un stream de eventos y depender de la forma exacta
del evento terminal `session.operation` — **que la documentación pública no detalla**.
El CLI pasa igualmente por el Gateway, pero absorbe handshake y versionado.

### 9.2 El contrato se inyecta en cada llamada

El adaptador lee `docs/PROMPT_PARA_OPENCLAW.md`, recorta el preámbulo dirigido al humano y
lo antepone al prompt de cada job. **No se pega en la config del VPS**: así el contrato
viaja versionado con el repo y no puede desincronizarse.

### 9.3 Lo que la documentación no especifica

El **esquema del envoltorio de `--json`**. El adaptador no asume ninguna clave: busca el
objeto del contrato §5.4 venga plano, anidado o dentro de un bloque markdown (probado
contra 6 formas distintas). Y trae una **sonda** para ver la forma real:

```bash
python3 adaptador_openclaw_vps.py --sonda "responde solo con {\"ok\":true}"
```

### 9.4 Manejo de errores

Probados uno a uno: código de salida ≠0 · salida sin el contrato · JSON que no valida
§5.4 · timeout. En **todos** los casos: job `FALLIDO` con motivo y `resultado` vacío.
Nunca datos inventados. Cada job usa `--session-key` propia para no heredar contexto.

### 9.5 El matiz de red

OpenClaw y el adaptador corren en el **host**; el backend en Docker. Dentro de un
contenedor `localhost` es el **propio contenedor**, así que la dirección correcta es
`host.docker.internal:8080` (cableada con `extra_hosts: host-gateway`). Eso obliga al
adaptador a escuchar en `0.0.0.0`, y por tanto **a cerrar el 8080 en `ufw`**.

---

## 10. Tests (49) — y cuáles son barreras

| Fichero | N.º | Qué cubre |
|---|---|---|
| `test_motor_financiero.py` | 15 | Casos calculados a mano, FX multi-divisa, NO_CALCULABLE |
| `test_motor_scoring.py` | 7 | Redistribución de pesos, multiplicador de riesgo país |
| `test_validacion_ingesta.py` | 7 | Válido, cuarentena, no-invención |
| `test_senales_no_reconocidas.py` | **8** | Códigos fuera de catálogo nunca se pierden |
| `test_blindaje_senales_ignoradas.py` | **6** | Un score con señales ignoradas nunca es COMPLETO |
| `test_anti_hardcode.py` | 2 | **Barrera** del Principio 2 |
| `test_analista_sin_numeros.py` | 4 | **Barrera** del Principio 1 |

Los dos últimos **no son comprobaciones, son barreras**. Si se ponen rojos no hay que
"arreglarlos": alguien cruzó un principio.

---

## 11. Lo que NO funciona / a medias (honesto)

Ordenado por lo que morderá antes.

1. **OpenClaw sin ejercitar** contra el agente real. Lo primero: la sonda de §9.3.
2. **Benchmarks provisionales y gruesos.** Los de nivel ciudad distorsionan el descuento
   (§6.1). Es lo que más cambiaría el ranking.
3. **VE vacío** por bloqueo de portales, y **sin catálogo de riesgos** (0 códigos): si
   algún día entran inmuebles de VE, ninguna señal de riesgo se aplicaría.
4. **`calidad_zona` y `margen_reforma` son proxies MVP** — y pesan **45% combinados** en
   el perfil de plusvalía. Ese perfil es más flojo que el de cashflow.
5. **`senales_no_reconocidas` es lista plana:** no distingue si el código ignorado era de
   riesgo o de oportunidad; marca `PARCIAL` en ambos casos (conservador a propósito).
6. **Dedup cross-portal heurística** (ciudad + precio ±5% + m² ±5%): solo marca, nunca
   fusiona. Dará falsos positivos y negativos.
7. **Tooltip de auditoría de métricas** usa `title` nativo: **no funciona en táctil**.
8. **Sin TLS extremo a extremo** (§7.3).
9. **RLS permisivo:** la barrera real es la auth de nginx, no la base de datos.

---

## 12. Próximos pasos

1. **Ejecutar la sonda de OpenClaw** en el VPS y activar `OPENCLAW_MODE=http`. Con eso el
   ciclo se cierra solo: el worker despacha por cron y los inmuebles entran sin tocar nada.
2. **Validar y afinar los benchmarks** de ES y DO a nivel barrio (§6.1).
3. **Cargar ADR y ocupación de Cap Cana** y activar el cálculo de corta estancia (§5).
4. **Definir `riesgos_pais` de VE** y encontrar una fuente de anuncios que no bloquee.
5. Convertir el tooltip de auditoría en un panel pulsable (táctil).

---

## 13. Mapa del código

El grafo del repo (`graphify-out/`) agrupa el sistema en 20 comunidades:

| Comunidad | Qué es |
|---|---|
| Motor Financiero Determinista | El cálculo puro (Principio 1) |
| Motor de Scoring Agnóstico | Combina componentes sin conocer su semántica |
| Validación de Señales | `validar_senales` + blindaje |
| Servicios de Cálculo | Orquesta métricas y scoring leyendo de BD |
| Cliente OpenClaw y Circuit Breaker | Resiliencia frente al scraper externo |
| Contrato de Ingesta OpenClaw | §5.4, validación por anuncio y cuarentena |
| Estado de Calibración por País | El checklist que explica por qué un país está vacío |
| API Inmuebles y Ranking · API Configuración | Superficie HTTP |
| Frontend React SPA · Ficha de Activo | Capa visual |

Regenerar con `/graphify --update` · informe en `graphify-out/GRAPH_REPORT.md` · grafo
navegable en `graphify-out/graph.html`.

---

## 14. Cómo levantar todo

**VPS (producción):** `git pull && docker compose --profile vps up -d --build`.
Detalle completo en `DESPLIEGUE.md`.

**Windows (desarrollo):** doble clic en `ARRANCAR.bat`; `PARAR.bat` para cerrar.
Detalle en `ARRANQUE.md`.

**Flujo de despliegue:** en Windows `git add -A && git commit && git push`; en el VPS
`git pull && docker compose --profile vps up -d --build`. **`--build` es imprescindible**:
sin él Docker reutiliza la imagen antigua y el código nuevo no entra. El `.env` no viaja
por git — el del VPS se mantiene allí, y tras cada `pull` conviene compararlo con
`.env.example`.
