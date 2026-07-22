# SaaS de Sourcing y Análisis de Inversión Inmobiliaria

Pipeline automatizado de descubrimiento, extracción, análisis financiero y
clasificación de oportunidades de inversión inmobiliaria en múltiples portales,
de forma agnóstica al portal.

## Dos principios inviolables

1. **Determinismo financiero.** Python calcula, Claude interpreta. Ningún número
   financiero sale de un LLM. Todo cálculo vive en `backend/dominio/motor_financiero.py`
   como función pura.
2. **Cero criterios de negocio en el código.** Ningún peso, umbral, porcentaje ni
   constante de negocio en un `.py`. Todo en base de datos, editable desde la UI.

## Stack

| Capa        | Tecnología                                  |
|-------------|---------------------------------------------|
| Backend     | Python 3.11+, FastAPI, Pydantic v2          |
| BD          | Supabase (PostgreSQL), migraciones SQL      |
| Cola/Jobs   | Tabla `jobs` + worker con APScheduler       |
| IA          | Anthropic API (`claude-sonnet-5`)           |
| Scraping    | OpenClaw (agente externo — NO se construye) |
| Frontend    | React 18 + TS + Vite + Tailwind (Fase 8-9)  |

## Puesta en marcha (desarrollo)

```bash
# 1. Base de datos local (Postgres en el puerto 5455)
docker compose up -d

# 2. Entorno Python
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1
# bash/macOS:          source .venv/bin/activate
pip install -r requirements.txt

# 3. Configuración
cp .env.example .env        # y rellena los valores (ANTHROPIC_API_KEY, etc.)

# 4. Migraciones + seeds
python scripts/aplicar_migraciones.py

# 5. API
uvicorn backend.main:app --reload --port 8000

# 6. Worker de jobs (proceso aparte, APScheduler)
python -m backend.worker.worker

# 7. Frontend
cd frontend && npm install && npm run dev   # http://localhost:5173
```

## Multi-país y arranque de datos

Sistema multi-país (ES / DO / VE). **Ningún país arranca hasta cargar sus datos**
(gastos de adquisición, costes de reforma, benchmarks, tipos de cambio) — es el
comportamiento correcto, no un fallo. Un dato ausente → el inmueble sale
`NO_CALCULABLE` y la pantalla **"Estado por país"** dice exactamente qué falta.
Los parámetros de arranque provisionales (riesgo país, umbrales, saturaciones)
llevan un flag `PROVISIONAL` visible; la UI avisa cuando un score los usa.

## OpenClaw

No se construye ningún scraper. `docs/PROMPT_PARA_OPENCLAW.md` es el system prompt
para pegar en tu OpenClaw del VPS, y `scripts/adaptador_openclaw_vps.py` el
adaptador HTTP que lo envuelve (`POST /jobs`, `GET /jobs/{id}`, `GET /health`).
En `OPENCLAW_MODE=manual` (por defecto) el prompt se copia desde el monitor de jobs
y el JSON de vuelta se pega ahí mismo.

## Estructura

```
backend/
  nucleo/          configuración, conexión a BD
  modelos/         modelos Pydantic v2 (validación estricta)
  repositorios/    acceso a datos (SQL parametrizado)
  dominio/         motor_financiero, motor_scoring (funciones puras, testadas)
  servicios/       constructor_prompt, analista_cualitativo, normalización
  integraciones/   openclaw_client
  api/             endpoints FastAPI (Fase 7)
  worker/          worker de jobs con APScheduler (Fase 7)
supabase/
  migrations/      esquema SQL versionado
  seeds/           datos de arranque (países, perfiles)
tests/             pytest (dominio, ingesta, repositorios)
```

## Estado del proyecto

Construcción por fases. Consulta `docs/DECISIONES.md` para el registro de
decisiones de negocio y de alcance ya tomadas.
