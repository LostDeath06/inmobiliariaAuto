# =============================================================================
#  Imagen del backend: sirve para las TRES piezas Python (API, worker, migraciones).
#  Es la misma imagen con distinto `command` en docker-compose: un solo build,
#  y garantiza que las tres corren exactamente el mismo código.
# =============================================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# curl: lo usa el healthcheck de compose para saber si la API responde.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Solo lo que hace falta en ejecución. `supabase/` va incluido porque el runner de
# migraciones lee de ahí los .sql versionados y los seeds.
COPY backend/ ./backend/
COPY scripts/ ./scripts/
COPY supabase/ ./supabase/
COPY pyproject.toml ./

# No root.
RUN useradd -m -u 1000 app && chown -R app:app /app
USER app

EXPOSE 8000

# Por defecto la API. El worker y las migraciones sobreescriben `command` en compose.
CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
