-- =============================================================================
-- 0003  Tablas de configuración  —  AQUÍ VIVE EL NEGOCIO (multi-país)
-- =============================================================================

-- Países.
CREATE TABLE paises (
    codigo  CHAR(2) PRIMARY KEY,          -- ISO-3166-1 alpha-2
    nombre  TEXT NOT NULL
);

-- Configuración global de la aplicación (clave-valor).
CREATE TABLE config_app (
    clave TEXT PRIMARY KEY,
    valor TEXT
);

-- -----------------------------------------------------------------------------
-- Perfiles de inversor. Pesos (agnósticos al país) y supuestos del inversor.
-- `tipo_interes_anual` NO va aquí: es dato de mercado por país (config_mercado_pais).
-- La normalización tampoco: sus saturaciones son por país.
-- -----------------------------------------------------------------------------
CREATE TABLE perfiles_inversor (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre            TEXT NOT NULL UNIQUE,
    descripcion       TEXT,
    activo            BOOLEAN NOT NULL DEFAULT TRUE,
    es_predeterminado BOOLEAN NOT NULL DEFAULT FALSE,
    -- { "rentabilidad_neta": 0.40, "descuento_mercado": 0.15, ... } (suman 1.0)
    pesos             JSONB NOT NULL DEFAULT '{}'::jsonb,
    -- { "ltv": 0.70, "plazo_anos": 25, "vacancia_pct": 0.05, "gastos_gestion_pct": 0.08 }
    supuestos         JSONB NOT NULL DEFAULT '{}'::jsonb,
    propietario_id    UUID,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX ux_perfil_predeterminado
    ON perfiles_inversor (COALESCE(propietario_id, '00000000-0000-0000-0000-000000000000'::uuid))
    WHERE es_predeterminado;

CREATE TRIGGER trg_perfiles_updated
    BEFORE UPDATE ON perfiles_inversor
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- -----------------------------------------------------------------------------
-- Configuración de mercado por país. Datos de mercado (no preferencia del
-- inversor) y anclajes de normalización. Cada parámetro provisional lleva su
-- `*_estado` (PROVISIONAL | VALIDADO); la UI avisa cuando un score usa provisionales.
-- -----------------------------------------------------------------------------
CREATE TABLE config_mercado_pais (
    pais                     CHAR(2) PRIMARY KEY REFERENCES paises(codigo),
    monedas_nativas          TEXT[] NOT NULL DEFAULT '{}',   -- p.ej. {'DOP','USD'}
    -- Tipo de interés hipotecario de referencia (dato de mercado, B8).
    tipo_interes_anual       NUMERIC(6,4),                   -- NULL = pendiente
    tipo_interes_estado      estado_parametro NOT NULL DEFAULT 'PROVISIONAL',
    -- Tope de financiación por país (VE al contado = 0). NULL = sin tope.
    ltv_max                  NUMERIC(4,3),
    ltv_max_estado           estado_parametro NOT NULL DEFAULT 'PROVISIONAL',
    -- Riesgo país como multiplicador: score_final = score_bruto * (1 - riesgo_pais).
    riesgo_pais              NUMERIC(4,3) NOT NULL DEFAULT 0,
    riesgo_pais_estado       estado_parametro NOT NULL DEFAULT 'PROVISIONAL',
    -- Saturaciones de normalización (fracción). rentabilidad_neta.max, descuento.max.
    sat_rentabilidad_neta    NUMERIC(6,4),
    sat_rentabilidad_estado  estado_parametro NOT NULL DEFAULT 'PROVISIONAL',
    sat_descuento_mercado    NUMERIC(6,4),
    sat_descuento_estado     estado_parametro NOT NULL DEFAULT 'PROVISIONAL',
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_config_mercado_updated
    BEFORE UPDATE ON config_mercado_pais
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- -----------------------------------------------------------------------------
-- Umbrales por (perfil, país). score_descarte VALIDADO=30 en los tres países;
-- roi_neto_minimo y descuento_minimo_interes PROVISIONALES.
-- -----------------------------------------------------------------------------
CREATE TABLE umbrales_perfil_pais (
    perfil_id                     UUID NOT NULL REFERENCES perfiles_inversor(id) ON DELETE CASCADE,
    pais                          CHAR(2) NOT NULL REFERENCES paises(codigo),
    score_descarte                NUMERIC(6,2) NOT NULL DEFAULT 30,
    score_descarte_estado         estado_parametro NOT NULL DEFAULT 'VALIDADO',
    roi_neto_minimo               NUMERIC(6,4),
    roi_neto_minimo_estado        estado_parametro NOT NULL DEFAULT 'PROVISIONAL',
    descuento_minimo_interes      NUMERIC(6,4),
    descuento_minimo_estado       estado_parametro NOT NULL DEFAULT 'PROVISIONAL',
    updated_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (perfil_id, pais)
);

CREATE TRIGGER trg_umbrales_updated
    BEFORE UPDATE ON umbrales_perfil_pais
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- -----------------------------------------------------------------------------
-- Tipos de cambio. Carga MANUAL desde la UI (sin feeds). Convierte Python.
-- Sin tasa disponible → la conversión a moneda de referencia sale PARCIAL.
-- -----------------------------------------------------------------------------
CREATE TABLE tipos_cambio (
    moneda_origen  CHAR(3) NOT NULL,       -- ISO 4217
    moneda_destino CHAR(3) NOT NULL,
    tasa           NUMERIC(18,8) NOT NULL, -- 1 origen = `tasa` destino
    fuente         TEXT,
    fecha          DATE NOT NULL,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (moneda_origen, moneda_destino, fecha)
);

-- -----------------------------------------------------------------------------
-- Catálogo de riesgos/oportunidades (en BD, no enum rígido) y su aplicación por
-- país. Para ES se siembra lo aprobado; DO y VE quedan vacíos (pendiente).
-- -----------------------------------------------------------------------------
CREATE TABLE catalogo_riesgos (
    codigo      TEXT PRIMARY KEY,
    clase       clase_senal NOT NULL,
    descripcion TEXT
);

CREATE TABLE riesgos_pais (
    pais           CHAR(2) NOT NULL REFERENCES paises(codigo),
    codigo         TEXT NOT NULL REFERENCES catalogo_riesgos(codigo),
    es_eliminatorio BOOLEAN NOT NULL DEFAULT FALSE,  -- descarte duro
    penalizacion   NUMERIC(6,2),   -- puntos que resta si es ponderable (negativo)
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (pais, codigo)
);

CREATE TRIGGER trg_riesgos_pais_updated
    BEFORE UPDATE ON riesgos_pais
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- -----------------------------------------------------------------------------
-- Costes de reforma €/nativa por m² por nivel y país. VACÍA (dato pendiente).
-- -----------------------------------------------------------------------------
CREATE TABLE costes_reforma (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pais          CHAR(2) NOT NULL REFERENCES paises(codigo),
    nivel_reforma nivel_reforma NOT NULL,
    coste_m2      NUMERIC(14,2),          -- en moneda nativa del país; NULL = ausente
    moneda        CHAR(3),
    fuente        TEXT,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pais, nivel_reforma)
);

CREATE TRIGGER trg_costes_reforma_updated
    BEFORE UPDATE ON costes_reforma
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- -----------------------------------------------------------------------------
-- Gastos de adquisición por país/región. VACÍA (dato pendiente en los 3 países).
-- -----------------------------------------------------------------------------
CREATE TABLE gastos_adquisicion (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pais       CHAR(2) NOT NULL REFERENCES paises(codigo),
    region     TEXT NOT NULL DEFAULT '',
    concepto   TEXT NOT NULL,
    tipo       tipo_gasto_adquisicion NOT NULL,
    valor      NUMERIC(14,6),             -- % (0.06) o importe fijo; NULL = ausente
    moneda     CHAR(3),                   -- para FIJO en moneda nativa
    fuente     TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pais, region, concepto)
);

CREATE TRIGGER trg_gastos_adquisicion_updated
    BEFORE UPDATE ON gastos_adquisicion
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- -----------------------------------------------------------------------------
-- Benchmarks de zona (datos de mercado). VACÍA (dato pendiente).
-- -----------------------------------------------------------------------------
CREATE TABLE benchmarks_zona (
    id                            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pais                          CHAR(2) NOT NULL REFERENCES paises(codigo),
    ciudad                        TEXT NOT NULL,
    barrio                        TEXT,
    moneda                        CHAR(3),
    precio_m2_venta_medio         NUMERIC(14,2),
    precio_m2_alquiler_medio      NUMERIC(14,2),
    rentabilidad_bruta_media_zona NUMERIC(6,4),
    fuente                        TEXT,
    fecha_dato                    DATE,
    updated_at                    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX ux_benchmark_zona
    ON benchmarks_zona (pais, ciudad, COALESCE(barrio, ''));

CREATE TRIGGER trg_benchmarks_zona_updated
    BEFORE UPDATE ON benchmarks_zona
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- -----------------------------------------------------------------------------
-- Portales.
-- -----------------------------------------------------------------------------
CREATE TABLE portales (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre                TEXT NOT NULL,
    url_raiz              TEXT NOT NULL UNIQUE,
    pais                  CHAR(2) REFERENCES paises(codigo),
    activo                BOOLEAN NOT NULL DEFAULT TRUE,
    notas_extraccion      TEXT,
    tasa_exito_historica  NUMERIC(5,4),
    propietario_id        UUID,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_portales_updated
    BEFORE UPDATE ON portales
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
