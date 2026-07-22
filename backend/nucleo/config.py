"""Configuración de la aplicación cargada desde variables de entorno.

No contiene ningún criterio de negocio: solo parámetros técnicos (conexiones,
timeouts, modo de operación). Los pesos, umbrales y costes viven en base de datos.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Base de datos
    database_url: str = "postgresql://inmo:inmo@localhost:5455/inmobiliaria"
    db_pool_min: int = 2
    db_pool_max: int = 10

    # Anthropic (analista cualitativo)
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"
    anthropic_max_tokens: int = 4096

    # OpenClaw
    openclaw_mode: str = "manual"  # http | manual
    openclaw_base_url: str = ""
    openclaw_api_key: str | None = None
    openclaw_timeout_segundos: int = 900
    openclaw_max_reintentos: int = 3
    openclaw_limite_anuncios: int = 50

    # Worker de jobs (APScheduler)
    worker_intervalo_sondeo_segundos: int = 15
    worker_jobs_concurrentes: int = 3

    # Aplicación
    entorno: str = "desarrollo"
    log_nivel: str = "INFO"
    api_host: str = "0.0.0.0"
    api_puerto: int = 8000

    # Multi-tenant preparado, no implementado (decisión 4A)
    propietario_por_defecto: str = "00000000-0000-0000-0000-000000000001"


@lru_cache
def obtener_config() -> Config:
    """Devuelve la configuración (cacheada) del proceso."""
    return Config()
