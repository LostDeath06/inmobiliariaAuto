# Graph Report - C:\Users\chris\inmobiliariaAuto  (2026-07-23)

## Corpus Check
- 109 files · ~51,344 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 877 nodes · 2050 edges · 68 communities (65 shown, 3 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 185 edges (avg confidence: 0.63)
- Token cost: 438,352 input · 0 output

## Community Hubs (Navigation)
- Frontend React SPA
- API Perfiles y Métricas
- Dependencias NPM Frontend
- Motor Financiero Determinista
- Repositorios de Consulta
- Servicios de Cálculo
- Ficha de Activo (UI)
- Configuración TypeScript
- Cliente OpenClaw y Circuit Breaker
- Modelos de Configuración
- Arranque y Conexión a BD
- Estado de Calibración por País
- API Inmuebles y Ranking
- API Configuración de Mercado
- Motor de Scoring Agnóstico
- Contrato de Ingesta OpenClaw
- Repositorio de Análisis
- Modelos del Pipeline
- Repositorio de Jobs
- Validación de Señales
- Vista Ranking Tema Oscuro
- Ficha con Doble Perfil
- Repositorios de País
- Vista Ranking Tema Claro
- Despacho de Jobs
- Enumeraciones del Dominio
- Principios Rectores del Proyecto
- Configuración por País
- API de Jobs
- Constructor de Prompt
- Conversión de Divisa
- Orquestación del Pipeline
- Monitor de Señales
- Arquitectura de Despliegue VPS
- Repositorio Config Mercado
- Analista Cualitativo Claude
- Ingesta y Normalización
- Datos Ausentes y NO_CALCULABLE
- Adaptador OpenClaw VPS
- Stack y Decisiones Técnicas
- Worker APScheduler
- API Portales y Búsquedas
- Repositorio de Perfiles
- Catálogo de Riesgos y Señales
- Decisiones de Ingesta Multi-País
- Servicios Docker Compose
- Repositorio de Portales
- Configuración Build Vite
- Test Anti-Hardcode
- Test Analista Sin Números
- Pool de Conexiones
- Migraciones y Seeds
- Salvaguardas del Ranking
- Estado Operativo España
- Entrypoint Auth Docker
- Raíz del Proyecto

## God Nodes (most connected - your core abstractions)
1. `a_modelo()` - 45 edges
2. `obtener_uno()` - 42 edges
3. `AnalisisCualitativo` - 36 edges
4. `a_modelos()` - 34 edges
5. `ModeloBase` - 33 edges
6. `CalidadDato` - 27 edges
7. `Inmueble` - 26 edges
8. `obtener_todos()` - 26 edges
9. `NivelReforma` - 25 edges
10. `calcular_metricas()` - 22 edges

## Surprising Connections (you probably didn't know these)
- `Regla de oro: null antes que invencion` --semantically_similar_to--> `No se inventan datos (linea roja #3)`  [INFERRED] [semantically similar]
  docs/PROMPT_PARA_OPENCLAW.md → ARRANQUE.md
- `Principio 1: determinismo financiero` --semantically_similar_to--> `Python calcula, Claude interpreta`  [INFERRED] [semantically similar]
  README.md → ARRANQUE.md
- `Principio 2: cero criterios de negocio en el codigo` --semantically_similar_to--> `Cero criterios de negocio en el codigo`  [INFERRED] [semantically similar]
  README.md → ARRANQUE.md
- `errores_navegacion y advertencias (reportar, nunca abortar)` --semantically_similar_to--> `Cuarentena de anuncios invalidos en la ingesta`  [INFERRED] [semantically similar]
  docs/PROMPT_PARA_OPENCLAW.md → ARRANQUE.md
- `Worker en contenedor aparte de la API` --conceptually_related_to--> `Decision 7A: worker con APScheduler, sin Redis ni Celery`  [INFERRED]
  DESPLIEGUE.md → docs/DECISIONES.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Flujo completo de extraccion a ranking** — docs_prompt_para_openclaw_agente_extraccion, arranque_modo_manual_openclaw, docs_prompt_para_openclaw_esquema_salida, arranque_cuarentena_anuncios, arranque_normalizacion_fx_previa, docs_decisiones_validar_senales, docs_decisiones_pesos_perfiles, docs_decisiones_salvaguardas_ranking [INFERRED 0.85]
- **Blindaje contra senales fuera de catalogo** — docs_decisiones_validar_senales, docs_decisiones_senales_no_reconocidas, docs_decisiones_ajustar_por_senales_ignoradas, arranque_riesgos_pais_vacios_do_ve, arranque_sesgo_al_alza_del_fallo_silencioso, arranque_estado_por_pais [EXTRACTED 1.00]
- **Cuatro piezas del stack VPS con arranque encadenado** — docker_compose_postgres, docker_compose_migraciones, docker_compose_backend, docker_compose_worker, docker_compose_frontend, docker_compose_perfil_vps [EXTRACTED 1.00]
- **Señales de transparencia del score en el ranking** — docs_capturas_01_ranking_oscuro_calidad_dato, docs_capturas_01_ranking_oscuro_marca_prov, docs_capturas_01_ranking_oscuro_marca_senal_ignorada, docs_capturas_01_ranking_oscuro_sin_riesgo_pais_toggle [INFERRED 0.85]
- **Controles de filtrado que condicionan el ranking mostrado** — docs_capturas_01_ranking_oscuro_perfil_de_inversor, docs_capturas_01_ranking_oscuro_filtro_pais, docs_capturas_01_ranking_oscuro_sin_riesgo_pais_toggle, docs_capturas_01_ranking_oscuro_tabla_ranking [INFERRED 0.85]
- **Ranking Scoring Control Set (profile + country + risk toggle drive score ordering)** — docs_capturas_02_ranking_claro_perfil_de_inversor_selector, docs_capturas_02_ranking_claro_pais_filter, docs_capturas_02_ranking_claro_sin_riesgo_pais_toggle, docs_capturas_02_ranking_claro_score_total, docs_capturas_02_ranking_claro_ranking_table [INFERRED 0.85]
- **Per-Row Trust and Provenance Signals** — docs_capturas_02_ranking_claro_calidad_indicator, docs_capturas_02_ranking_claro_marcas_column, docs_capturas_02_ranking_claro_score_bar_indicator, docs_capturas_02_ranking_claro_inmueble_record [INFERRED 0.75]
- **Patrón de trazabilidad y procedencia de cada cifra mostrada** — docs_capturas_03_ficha_senal_fuera_de_catalogo_senales_fuera_del_catalogo, docs_capturas_03_ficha_senal_fuera_de_catalogo_badge_prov, docs_capturas_03_ficha_senal_fuera_de_catalogo_analisis_demo, docs_capturas_03_ficha_senal_fuera_de_catalogo_tooltip_formula_inputs, docs_capturas_03_ficha_senal_fuera_de_catalogo_calidad_del_dato [INFERRED 0.85]
- **Pipeline de scoring del activo: datos crudos, componentes, perfiles y score final** — docs_capturas_03_ficha_senal_fuera_de_catalogo_panel_datos, docs_capturas_03_ficha_senal_fuera_de_catalogo_componentes_score, docs_capturas_03_ficha_senal_fuera_de_catalogo_metricas_financieras, docs_capturas_03_ficha_senal_fuera_de_catalogo_cashflow_corto_plazo, docs_capturas_03_ficha_senal_fuera_de_catalogo_plusvalia_largo_plazo, docs_capturas_03_ficha_senal_fuera_de_catalogo_score_bruto_total [INFERRED 0.85]
- **Flujo de valoracion del activo: datos crudos -> componentes -> score por perfil -> analisis cualitativo** — docs_capturas_04_ficha_historico_precios_panel_datos, docs_capturas_04_ficha_historico_precios_componentes_score, docs_capturas_04_ficha_historico_precios_score_por_perfil, docs_capturas_04_ficha_historico_precios_analisis_cualitativo [INFERRED 0.85]
- **Senal de oportunidad temporal: historico de precios, moneda nativa y deteccion de rebaja/venta urgente** — docs_capturas_04_ficha_historico_precios_historico_de_precios, docs_capturas_04_ficha_historico_precios_moneda_nativa, docs_capturas_04_ficha_historico_precios_deteccion_precio_rebajado, docs_capturas_04_ficha_historico_precios_componentes_score [INFERRED 0.85]
- **LLM Signal Extraction Quality-Control Flow** — docs_capturas_05_monitor_senales_claude_llm_extractor, docs_capturas_05_monitor_senales_country_signal_catalog, docs_capturas_05_monitor_senales_out_of_catalog_signal, docs_capturas_05_monitor_senales_human_review_loop, docs_capturas_05_monitor_senales_humedades_estructurales_code [INFERRED 0.85]
- **Monitor Dashboard Layout Composition** — docs_capturas_05_monitor_senales_screen, docs_capturas_05_monitor_senales_top_nav, docs_capturas_05_monitor_senales_senales_fuera_de_catalogo_panel, docs_capturas_05_monitor_senales_jobs_panel, docs_capturas_05_monitor_senales_dark_theme_ui [EXTRACTED 1.00]
- **Bloques de calibración requeridos por país** — docs_capturas_06_estado_pais_sin_catalogo_riesgos_tipo_interes, docs_capturas_06_estado_pais_sin_catalogo_riesgos_riesgo_pais, docs_capturas_06_estado_pais_sin_catalogo_riesgos_saturaciones, docs_capturas_06_estado_pais_sin_catalogo_riesgos_gastos_adquisicion, docs_capturas_06_estado_pais_sin_catalogo_riesgos_costes_reforma, docs_capturas_06_estado_pais_sin_catalogo_riesgos_benchmarks_zona, docs_capturas_06_estado_pais_sin_catalogo_riesgos_riesgos_pais, docs_capturas_06_estado_pais_sin_catalogo_riesgos_tipos_cambio [EXTRACTED 1.00]
- **Países monitorizados en el panel de estado** — docs_capturas_06_estado_pais_sin_catalogo_riesgos_pais_es, docs_capturas_06_estado_pais_sin_catalogo_riesgos_pais_do, docs_capturas_06_estado_pais_sin_catalogo_riesgos_pais_ve, docs_capturas_06_estado_pais_sin_catalogo_riesgos_checklist_operatividad_pais [EXTRACTED 1.00]
- **Semáforo de calidad de datos (operativo / provisional / aviso)** — docs_capturas_06_estado_pais_sin_catalogo_riesgos_estado_operativo, docs_capturas_06_estado_pais_sin_catalogo_riesgos_calibracion_incompleta, docs_capturas_06_estado_pais_sin_catalogo_riesgos_marca_provisional, docs_capturas_06_estado_pais_sin_catalogo_riesgos_aviso_sin_catalogo_riesgos [INFERRED 0.85]

## Communities (68 total, 3 thin omitted)

### Community 0 - "Frontend React SPA"
Cohesion: 0.09
Nodes (36): api, PAISES, BotonTema(), enlaces, router, celdaVacia(), ConfigMercado(), DesgloseChart() (+28 more)

### Community 1 - "API Perfiles y Métricas"
Cohesion: 0.08
Nodes (38): actualizar(), eliminar(), obtener(), UUID, Endpoints de perfiles de inversor., CalidadDato, MetricasFinancieras, Modelo de `metricas_financieras` (salida del motor determinista). (+30 more)

### Community 2 - "Dependencias NPM Frontend"
Cohesion: 0.06
Nodes (34): autoprefixer, dependencies, react, react-dom, react-router-dom, recharts, devDependencies, autoprefixer (+26 more)

### Community 3 - "Motor Financiero Determinista"
Cohesion: 0.13
Nodes (33): calcular_metricas(), _convertir(), _cuota_hipoteca_anual(), EntradaFinanciera, GastoAdquisicionEntrada, Decimal, Motor financiero determinista.  PRINCIPIO 1: Python calcula, Claude interpreta., Cuota anual por amortización francesa. Exponente entero → determinista. (+25 more)

### Community 4 - "Repositorios de Consulta"
Cohesion: 0.11
Nodes (31): Any, catalogo(), listar_costes(), listar_mercado(), ficha_inmueble(), Ficha completa: datos, métricas con auditoría, análisis y scores por perfil., HistoricoPrecio, obtener_todos() (+23 more)

### Community 5 - "Servicios de Cálculo"
Cohesion: 0.16
Nodes (24): AnalisisCualitativo, Juicio cualitativo de Claude sobre un inmueble. §8.2., Inmueble, calcular(), calcular_y_guardar(), construir_entrada(), Servicio de cálculo financiero.  Orquesta: reúne los datos (inmueble, análisis,, Calcula con el perfil dado y persiste la fila canónica de métricas. (+16 more)

### Community 6 - "Ficha de Activo (UI)"
Cohesion: 0.13
Nodes (25): Acción Recalcular, Acción Ver anuncio (enlace al portal origen), Alucinación del modelo (hipótesis de código inventado), Análisis cualitativo (Claude · solo juicio, cero cifras), Análisis de DEMO (no procede de Claude), Badge PROV (score provisional), Calidad del dato (COMPLETO / parcial), Perfil CASHFLOW_CORTO_PLAZO (+17 more)

### Community 7 - "Configuración TypeScript"
Cohesion: 0.09
Nodes (22): compilerOptions, allowImportingTsExtensions, isolatedModules, jsx, lib, module, moduleResolution, noEmit (+14 more)

### Community 8 - "Cliente OpenClaw y Circuit Breaker"
Cohesion: 0.16
Nodes (9): _CircuitBreaker, CircuitoAbierto, OpenClawClient, OpenClawError, Envía un job. Devuelve el openclaw_job_id. En modo manual no aplica., Fallo al hablar con OpenClaw., El circuit breaker está abierto: OpenClaw se considera caído., Exception (+1 more)

### Community 9 - "Modelos de Configuración"
Cohesion: 0.38
Nodes (19): ModeloBase, Base de todos los modelos.      `extra="forbid"`: cualquier campo no declarado e, BenchmarkZona, CatalogoRiesgo, ConfigApp, ConfigMercadoPais, CosteReforma, GastoAdquisicion (+11 more)

### Community 10 - "Arranque y Conexión a BD"
Cohesion: 0.16
Nodes (15): ciclo_vida(), Health check + estado de OpenClaw., salud(), cerrar_pool(), Gestión del pool de conexiones a PostgreSQL (asyncpg).  Falla ruidosamente: si n, Cierra el pool (al apagar la aplicación)., Config, obtener_config() (+7 more)

### Community 11 - "Estado de Calibración por País"
Cohesion: 0.15
Nodes (19): Aviso: Sin catálogo de riesgos (infra-penalización), benchmarks_zona, Estado Calibración incompleta (badge rojo), Captura: Estado por país sin catálogo de riesgos, Checklist de operatividad por país, costes_reforma (€/m² por nivel COSMETICA/MEDIA/INTEGRAL), Fail-closed: ningún país arranca sin sus datos cargados, gastos_adquisicion (+11 more)

### Community 12 - "API Inmuebles y Ranking"
Cohesion: 0.16
Nodes (17): _dec(), historico_precios(), listar_inmuebles(), Decimal, UUID, ranking(), Endpoints de inmuebles, ranking y operaciones del pipeline., Solo scores (sin reanalizar): útil tras cambiar configuración de mercado. (+9 more)

### Community 13 - "API Configuración de Mercado"
Cohesion: 0.18
Nodes (14): actualizar_umbrales(), cargar_tasa(), _dec(), establecer_benchmark(), establecer_coste(), establecer_gasto(), establecer_riesgo(), fijar_moneda_ref() (+6 more)

### Community 14 - "Motor de Scoring Agnóstico"
Cohesion: 0.21
Nodes (15): calcular_score(), _normalizar(), Decimal, Motor de scoring agnóstico.  PRINCIPIO 2: no conoce la semántica de ningún compo, Mapea un valor crudo a 0–100 según la curva (lineal, con dirección)., Calcula el score agnósticamente. Ver reglas en el docstring del módulo., ResultadoScoring, Tests del motor de scoring (agnóstico, puro). (+7 more)

### Community 15 - "Contrato de Ingesta OpenClaw"
Cohesion: 0.20
Nodes (15): TipoAnunciante, AnuncioOpenClaw, BusquedaEjecutada, Contrato de salida de OpenClaw (§5.4, multi-divisa).  El prompt que se le envía, Un anuncio individual extraído por OpenClaw. Ver §5.4., Resumen de la búsqueda que OpenClaw ejecutó. Ver §5.4., Sobre completo devuelto por OpenClaw. Ver §5.4.      `anuncios` se recibe como c, SobreScraping (+7 more)

### Community 16 - "Repositorio de Análisis"
Cohesion: 0.18
Nodes (16): ejecutar(), guardar(), marcar_fallido(), obtener(), obtener_hash(), UUID, Repositorio de análisis cualitativos (salida de Claude)., Marca el inmueble como ANALISIS_FALLIDO sin abortar el lote (§8.1). (+8 more)

### Community 17 - "Modelos del Pipeline"
Cohesion: 0.21
Nodes (13): Modelo base Pydantic v2 con validación estricta., AnuncioCrudoRegistro, AnuncioCuarentena, Modelos de las tablas del pipeline (multi-divisa)., Fila de `anuncios_crudos`. Inmutable, append-only., Fila de `anuncios_cuarentena` (2A)., guardar_crudo(), guardar_en_cuarentena() (+5 more)

### Community 18 - "Repositorio de Jobs"
Cohesion: 0.26
Nodes (14): EstadoJob, Job, a_modelo(), Record, Utilidades comunes de los repositorios., Convierte una fila de asyncpg en un modelo Pydantic, o None., actualizar(), crear() (+6 more)

### Community 19 - "Validación de Señales"
Cohesion: 0.24
Nodes (15): Cruza las señales de Claude contra el catálogo del país del inmueble.      - Un, validar_senales(), _analisis(), Endurecimiento del cruce de señales contra el catálogo del país.  El catálogo de, Nunca se pierde': el campo cruza ida y vuelta por JSON sin desaparecer., Un código inventado NO se pierde: acaba en `senales_no_reconocidas`., DO/VE aún sin `riesgos_pais`: cada código emitido es un aviso, no un silencio., `NINGUNA` significa 'sin señal': ni se aplica ni ensucia no_reconocidas. (+7 more)

### Community 20 - "Vista Ranking Tema Oscuro"
Cohesion: 0.17
Nodes (16): Barra de score con codificación por color (verde/azul/gris), Calidad del dato (COMPLETO / PARCIAL), CASHFLOW_CORTO_PLAZO (perfil de inversor activo), Filtro de país (valor Global), Inmueble (título, ciudad, código de país), Marca PROV (score provisional), Marca SEÑAL IGNORADA, Mercado español: Madrid, Valencia, Bilbao (ES, precios en EUR) (+8 more)

### Community 21 - "Ficha con Doble Perfil"
Cohesion: 0.19
Nodes (16): Accion Recalcular / Ver anuncio, Analisis Cualitativo (Claude: solo juicio, cero cifras), Banner de datos DEMO (Analisis de DEMO para revision visual; no procede de Claude), Calidad del dato (COMPLETO / PROV), Perfil CASHFLOW_CORTO_PLAZO, Componentes del Score (calidad_zona, riesgo_activo, margen_reforma, aptitud_alquiler, descuento_mercado, rentabilidad_neta, oportunidad_temporal), Desglose del Score (contribucion de cada componente), Deteccion de PRECIO_REBAJADO / VENTA_URGENTE (+8 more)

### Community 22 - "Repositorios de País"
Cohesion: 0.16
Nodes (13): listar_benchmarks(), listar_gastos(), riesgos_pais(), listar_benchmarks_zona(), listar_gastos_adquisicion(), listar_riesgos_pais(), listar(), Repositorio de países. (+5 more)

### Community 23 - "Vista Ranking Tema Claro"
Cohesion: 0.17
Nodes (15): Data Quality Indicator (CALIDAD: COMPLETO / PARCIAL), CASHFLOW_CORTO_PLAZO Investor Profile, Inmueble Record (title, city, country, precio EUR, m2), Marcas Column (PROV provenance badge), Country Filter (PAIS, value Global), Investor Profile Selector (PERFIL DE INVERSOR), Primary Navigation (Ranking, Estado por pais, Perfiles, Configuracion, Portales, Monitor), Ranking Screen (Light Theme) (+7 more)

### Community 24 - "Despacho de Jobs"
Cohesion: 0.22
Nodes (12): JobScraping, Cliente HTTP para OpenClaw (§5.3).  OpenClaw YA EXISTE (agente externo en un VPS, ejecutar_busqueda(), ingestar_resultado_manual(), procesar_job_http(), UUID, Despacho de jobs a OpenClaw e ingesta del resultado.  Genera el job y el prompt;, Crea un job, genera el prompt y lo despacha según el modo. (+4 more)

### Community 25 - "Enumeraciones del Dominio"
Cohesion: 0.41
Nodes (11): Salida del analista cualitativo (Claude). §8.2.  SOLO juicio cualitativo estruct, AptoTernario, CalidadDescripcion, CoherenciaPrecio, EstadoConservacion, NivelConfianza, Enumeraciones del dominio, espejo de los ENUM de PostgreSQL.  Son categorías est, Tipologia (+3 more)

### Community 26 - "Principios Rectores del Proyecto"
Cohesion: 0.17
Nodes (13): Cero criterios de negocio en el codigo, Parametros PROVISIONAL vs VALIDADO, Pipeline de sourcing y ranking inmobiliario, calidad_zona y margen_reforma como proxies MVP, Python calcula, Claude interpreta, tests/test_analista_sin_numeros.py, tests/test_anti_hardcode.py, Configuracion por eje: perfil, pais, perfil x pais (+5 more)

### Community 27 - "Configuración por País"
Cohesion: 0.27
Nodes (12): actualizar_mercado(), obtener_moneda_ref(), UmbralPerfilPais, actualizar_config_mercado(), establecer_umbrales(), listar_umbrales(), moneda_referencia(), obtener_config_app() (+4 more)

### Community 28 - "API de Jobs"
Cohesion: 0.26
Nodes (12): cancelar(), cuarentena(), listar(), obtener(), obtener_prompt(), UUID, Endpoints de jobs (incluye modo manual de OpenClaw)., Modo manual: devuelve el prompt para copiar. (+4 more)

### Community 29 - "Constructor de Prompt"
Cohesion: 0.26
Nodes (11): Busqueda, crear(), marcar_ejecutada(), obtener(), Decimal, UUID, Repositorio de búsquedas., construir() (+3 more)

### Community 30 - "Conversión de Divisa"
Cohesion: 0.22
Nodes (11): cargar_tasa(), obtener_tasa(), Decimal, Tasa más reciente para el par. None si no hay ninguna (→ conversión PARCIAL)., convertir(), convertir_dict(), Decimal, Conversión de divisa. La hace Python con la tasa de BD, nunca Claude, nunca hard (+3 more)

### Community 31 - "Orquestación del Pipeline"
Cohesion: 0.24
Nodes (12): _codigos_pais(), procesar_inmueble(), procesar_inmuebles(), UUID, Orquestación del pipeline post-ingesta: análisis cualitativo → métricas → scores, Tras cambiar pesos: recalcula los scores del perfil sobre todos los inmuebles., Códigos de riesgo (del país) y oportunidad (del catálogo) para el analista., Análisis (con caché por hash) + métricas + scores de un inmueble. (+4 more)

### Community 32 - "Monitor de Señales"
Cohesion: 0.22
Nodes (13): Claude LLM Signal Extractor, Per-Country Signal Catalog, Dark Theme Dashboard UI with Theme Toggle, Empty State Pattern (Sin jobs todavia), Human Review Loop for Unrecognized Signals, HUMEDADES_ESTRUCTURALES Signal Code, Job Metrics Columns (Estado, Validos, Cuar., Coste USD), Jobs Panel (auto-refresco cada 5 s) (+5 more)

### Community 33 - "Arquitectura de Despliegue VPS"
Cohesion: 0.17
Nodes (12): RLS permisivo y CORS *, Arquitectura de despliegue VPS, Flujo de actualizacion git pull + --build, nginx con auth basica como unica puerta, Resolucion DNS diferida del upstream backend en nginx, restart: unless-stopped en todas las piezas, Sin HTTPS (limitacion conocida), Servicio frontend (compose) (+4 more)

### Community 34 - "Repositorio Config Mercado"
Cohesion: 0.30
Nodes (11): obtener_uno(), establecer_benchmark(), establecer_coste_reforma(), establecer_gasto_adquisicion(), obtener_benchmark_zona(), obtener_coste_reforma(), Decimal, Repositorio de configuración de mercado: costes de reforma, gastos de adquisició (+3 more)

### Community 35 - "Analista Cualitativo Claude"
Cohesion: 0.23
Nodes (11): analizar(), _esquema(), _hash_contenido(), _prompt_usuario(), Analista cualitativo (Claude API).  PRINCIPIO 1: Claude SOLO emite juicio cualit, Llama a Claude y devuelve el análisis validado (o fallido)., Deduplica preservando el orden de aparición., ResultadoAnalisis (+3 more)

### Community 36 - "Ingesta y Normalización"
Cohesion: 0.30
Nodes (11): _a_decimal(), _fecha(), _hash(), _normalizar_anuncio(), procesar(), datetime, Decimal, UUID (+3 more)

### Community 37 - "Datos Ausentes y NO_CALCULABLE"
Cohesion: 0.22
Nodes (11): Benchmarks de zona (EUR/m2 venta y alquiler), Configuracion de mercado por pais, scripts/demo_datos_visuales.py (siembra de demo), Pantalla Estado por pais, Estado NO_CALCULABLE / PARCIAL del score, No se inventan datos (linea roja #3), riesgos_pais vacio en DO y VE, El fallo silencioso empuja el score al alza (+3 more)

### Community 38 - "Adaptador OpenClaw VPS"
Cohesion: 0.29
Nodes (9): _auth(), cancelar_job(), crear_job(), ejecutar_openclaw(), estado_job(), _procesar(), Adaptador HTTP para envolver OpenClaw en el VPS (entregable §14).  NO modifica O, SUSTITUIR: llama a tu OpenClaw real y devuelve el JSON del contrato §5.4. (+1 more)

### Community 39 - "Stack y Decisiones Técnicas"
Cohesion: 0.22
Nodes (10): OPENCLAW_MODE manual (copiar prompt / pegar JSON), host.docker.internal para OpenClaw en el host, Decision 8B: modelo claude-sonnet-5, Decision 7A: worker con APScheduler, sin Redis ni Celery, Agente de extraccion inmobiliaria multi-portal (system prompt), OpenClaw: no se construye ningun scraper, Stack tecnologico del proyecto, APScheduler==3.11.0 (worker de cron) (+2 more)

### Community 40 - "Worker APScheduler"
Cohesion: 0.33
Nodes (9): AsyncIOScheduler, _despachar_cron(), iniciar(), _principal(), _procesar_jobs_http(), _proxima_ejecucion(), datetime, Worker de jobs (APScheduler, sin Redis ni Celery — decisión 7A).  Sondea periódi (+1 more)

### Community 41 - "API Portales y Búsquedas"
Cohesion: 0.29
Nodes (9): crear_busqueda(), crear_portal(), _dec(), ejecutar_busqueda(), listar_busquedas(), listar_portales(), Decimal, UUID (+1 more)

### Community 42 - "Repositorio de Perfiles"
Cohesion: 0.42
Nodes (9): PerfilInversor, actualizar(), crear(), eliminar(), listar(), obtener(), obtener_predeterminado(), UUID (+1 more)

### Community 43 - "Catálogo de Riesgos y Señales"
Cohesion: 0.22
Nodes (9): ANALISIS_FALLIDO indistinguible en la UI, Catalogo de riesgos y oportunidades (18 codigos), scripts/probar_analista.py (prueba de humo de Claude), ajustar_por_senales_ignoradas() degrada a PARCIAL, riesgo_activo partido: eliminatorios vs ponderables, senales_no_reconocidas (migracion 0006), validar_senales() contra el catalogo del pais, campos_no_encontrados por anuncio (+1 more)

### Community 44 - "Decisiones de Ingesta Multi-País"
Cohesion: 0.31
Nodes (9): Cuarentena de anuncios invalidos en la ingesta, Dedup cross-portal heuristico, Normalizacion FX antes de calcular, Alcance multi-pais desde el dia uno (ES/DO/VE), precio + moneda ISO 4217 en vez de precio_eur, Registro de decisiones autoritativo, tipos_cambio en BD con carga manual, errores_navegacion y advertencias (reportar, nunca abortar) (+1 more)

### Community 45 - "Servicios Docker Compose"
Cohesion: 0.28
Nodes (9): Puerto Postgres 5455, Una sola imagen para API, worker y migraciones, Migraciones one-shot antes del backend, Worker en contenedor aparte de la API, Servicio backend (compose), Servicio migraciones (compose, one-shot), Servicio postgres (compose), Volumen datos_postgres (+1 more)

### Community 46 - "Repositorio de Portales"
Cohesion: 0.39
Nodes (8): Portal, crear(), listar(), listar_por_pais(), obtener(), UUID, Repositorio de portales., Todos los portales de un país, activos e inactivos. Los inactivos con notas

### Community 47 - "Configuración Build Vite"
Cohesion: 0.22
Nodes (8): compilerOptions, allowSyntheticDefaultImports, composite, module, moduleResolution, skipLibCheck, include, vite.config.ts

### Community 48 - "Test Anti-Hardcode"
Cohesion: 0.32
Nodes (7): Module, _literales_numericos_de_modulo(), Test anti-hardcode (protege el Principio 2).  Decisión 6A: acotado. Escanea SOLO, Devuelve (nombre, valor) de asignaciones de nivel de módulo cuyo valor sea     u, El propio test debe cazar un hardcode. Verificación del verificador., test_dominio_sin_constantes_de_negocio_a_nivel_de_modulo(), test_el_test_detecta_una_infraccion_real()

### Community 49 - "Test Analista Sin Números"
Cohesion: 0.38
Nodes (4): Test anti-números del analista (protege el Principio 1).  Verifica que el esquem, test_el_detector_caza_un_numero_real(), test_esquema_del_analista_no_tiene_campos_numericos(), _tipos_en_esquema()

### Community 50 - "Pool de Conexiones"
Cohesion: 0.33
Nodes (6): _init_conexion(), obtener_pool(), Connection, Registra JSON/JSONB como codec para trabajar con dicts de Python., Devuelve el pool de conexiones, creándolo la primera vez., Pool

### Community 51 - "Migraciones y Seeds"
Cohesion: 0.53
Nodes (5): _aplicar_migraciones(), _aplicar_seeds(), main(), Connection, Aplica las migraciones SQL versionadas y los seeds.  Uso:     python scripts/apl

### Community 52 - "Salvaguardas del Ranking"
Cohesion: 0.67
Nodes (3): riesgo_pais como multiplicador del score, Salvaguardas del ranking (filtro por pais, toggle sin riesgo pais), score_descarte = 30 en los tres paises

## Ambiguous Edges - Review These
- `Score Total (property ranking metric)` → `Data Quality Indicator (CALIDAD: COMPLETO / PARCIAL)`  [AMBIGUOUS]
  docs/capturas/02_ranking_claro.png · relation: conceptually_related_to
- `tipo_interes (tipo de interés hipotecario)` → `Score de inmueble`  [AMBIGUOUS]
  docs/capturas/06_estado_pais_sin_catalogo_riesgos.png · relation: conceptually_related_to

## Knowledge Gaps
- **86 isolated node(s):** `docker-entrypoint-auth.sh script`, `name`, `private`, `version`, `type` (+81 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Score Total (property ranking metric)` and `Data Quality Indicator (CALIDAD: COMPLETO / PARCIAL)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **What is the exact relationship between `tipo_interes (tipo de interés hipotecario)` and `Score de inmueble`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `CalidadDato` connect `API Perfiles y Métricas` to `Motor Financiero Determinista`, `Repositorios de Consulta`, `Servicios de Cálculo`, `Ingesta y Normalización`, `Motor de Scoring Agnóstico`, `Modelos del Pipeline`, `Repositorio de Jobs`, `Enumeraciones del Dominio`, `Constructor de Prompt`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Why does `AnalisisCualitativo` connect `Servicios de Cálculo` to `Analista Cualitativo Claude`, `Modelos de Configuración`, `Arranque y Conexión a BD`, `Repositorio de Análisis`, `Test Analista Sin Números`, `Validación de Señales`, `Enumeraciones del Dominio`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Why does `a_modelo()` connect `Repositorio de Jobs` to `API Perfiles y Métricas`, `Repositorio Config Mercado`, `Repositorios de Consulta`, `Repositorio de Perfiles`, `Repositorio de Portales`, `Repositorio de Análisis`, `Modelos del Pipeline`, `Configuración por País`, `Constructor de Prompt`, `Conversión de Divisa`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `AnalisisCualitativo` (e.g. with `ModeloBase` and `AptoTernario`) actually correct?**
  _`AnalisisCualitativo` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Are the 24 inferred relationships involving `ModeloBase` (e.g. with `AnalisisCualitativo` and `BenchmarkZona`) actually correct?**
  _`ModeloBase` has 24 INFERRED edges - model-reasoned connections that need verification._