-- =============================================================================
-- 0004  Tablas del pipeline (multi-país / multi-divisa)
-- =============================================================================

CREATE TABLE busquedas (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portal_id         UUID NOT NULL REFERENCES portales(id) ON DELETE CASCADE,
    ciudad            TEXT,
    presupuesto_min   NUMERIC(16,2),
    presupuesto_max   NUMERIC(16,2),
    moneda            CHAR(3),            -- moneda del presupuesto (ISO 4217)
    tipo_inmueble     TEXT,
    filtros_extra     JSONB NOT NULL DEFAULT '{}'::jsonb,
    activa            BOOLEAN NOT NULL DEFAULT TRUE,
    frecuencia_cron   TEXT,
    ultima_ejecucion  TIMESTAMPTZ,
    proxima_ejecucion TIMESTAMPTZ,
    propietario_id    UUID,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_busquedas_pendientes
    ON busquedas (proxima_ejecucion)
    WHERE activa AND frecuencia_cron IS NOT NULL;

CREATE TRIGGER trg_busquedas_updated
    BEFORE UPDATE ON busquedas
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE jobs (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    busqueda_id                 UUID NOT NULL REFERENCES busquedas(id) ON DELETE CASCADE,
    estado                      estado_job NOT NULL DEFAULT 'PENDIENTE',
    prompt_enviado              TEXT,
    openclaw_job_id             TEXT,
    intentos                    INT NOT NULL DEFAULT 0,
    error_mensaje               TEXT,
    tokens_entrada              INT,
    tokens_salida               INT,
    coste_estimado_usd          NUMERIC(12,6),
    total_resultados_detectados INT,
    total_anuncios_extraidos    INT,
    total_anuncios_validos      INT,
    total_anuncios_cuarentena   INT,
    extraccion_completa         BOOLEAN,
    iniciado_en                 TIMESTAMPTZ,
    finalizado_en               TIMESTAMPTZ,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_jobs_estado ON jobs (estado);
CREATE INDEX ix_jobs_busqueda ON jobs (busqueda_id);

CREATE TRIGGER trg_jobs_updated
    BEFORE UPDATE ON jobs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Anuncios crudos. INMUTABLE. APPEND-ONLY.
CREATE TABLE anuncios_crudos (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id         UUID NOT NULL REFERENCES jobs(id),
    url_anuncio    TEXT NOT NULL,
    payload_json   JSONB NOT NULL,
    hash_contenido TEXT NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_anuncios_crudos_job ON anuncios_crudos (job_id);
CREATE INDEX ix_anuncios_crudos_hash ON anuncios_crudos (hash_contenido);

CREATE TRIGGER trg_anuncios_crudos_inmutable
    BEFORE UPDATE OR DELETE ON anuncios_crudos
    FOR EACH ROW EXECUTE FUNCTION prohibir_modificacion();

-- Cuarentena (2A).
CREATE TABLE anuncios_cuarentena (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id              UUID NOT NULL REFERENCES jobs(id),
    url_anuncio         TEXT,
    payload_crudo       JSONB NOT NULL,
    errores_validacion  JSONB NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_cuarentena_job ON anuncios_cuarentena (job_id);

-- Inmuebles normalizados (multi-divisa).
CREATE TABLE inmuebles (
    id                             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    portal_id                      UUID NOT NULL REFERENCES portales(id),
    id_portal                      TEXT,
    url_anuncio                    TEXT NOT NULL,
    hash_deduplicacion             TEXT NOT NULL,
    titulo                         TEXT,
    precio                         NUMERIC(16,2),
    moneda                         CHAR(3),          -- ISO 4217 (nativa del anuncio)
    superficie_construida_m2       NUMERIC(10,2),
    superficie_util_m2             NUMERIC(10,2),
    habitaciones                   INT,
    banos                          INT,
    planta                         TEXT,
    tiene_ascensor                 BOOLEAN,
    ano_construccion               INT,
    certificado_energetico         TEXT,
    direccion_texto                TEXT,
    barrio                         TEXT,
    ciudad                         TEXT,
    provincia                      TEXT,
    pais                           CHAR(2),
    codigo_postal                  TEXT,
    latitud                        NUMERIC(10,7),
    longitud                       NUMERIC(10,7),
    descripcion_completa           TEXT,
    caracteristicas_listadas       TEXT[] NOT NULL DEFAULT '{}',
    urls_imagenes                  TEXT[] NOT NULL DEFAULT '{}',
    tipo_anunciante                tipo_anunciante,
    fecha_publicacion              TIMESTAMPTZ,
    gastos_comunidad_mes           NUMERIC(12,2),
    estado_calidad                 calidad_dato,
    posible_duplicado_cross_portal BOOLEAN NOT NULL DEFAULT FALSE,   -- 3A
    inmuebles_duplicados_ids       UUID[] NOT NULL DEFAULT '{}',
    primer_visto                   TIMESTAMPTZ NOT NULL DEFAULT now(),
    ultimo_visto                   TIMESTAMPTZ NOT NULL DEFAULT now(),
    propietario_id                 UUID,
    created_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (portal_id, hash_deduplicacion)
);

CREATE UNIQUE INDEX ux_inmueble_portal_idportal
    ON inmuebles (portal_id, id_portal)
    WHERE id_portal IS NOT NULL;

CREATE INDEX ix_inmuebles_ciudad ON inmuebles (ciudad);
CREATE INDEX ix_inmuebles_pais ON inmuebles (pais);
CREATE INDEX ix_inmuebles_precio ON inmuebles (precio);

CREATE TRIGGER trg_inmuebles_updated
    BEFORE UPDATE ON inmuebles
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Histórico de precios (en moneda nativa del inmueble).
CREATE TABLE historico_precios (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inmueble_id     UUID NOT NULL REFERENCES inmuebles(id) ON DELETE CASCADE,
    precio          NUMERIC(16,2) NOT NULL,
    moneda          CHAR(3),
    fecha_detectada TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_historico_inmueble ON historico_precios (inmueble_id, fecha_detectada);

-- Análisis cualitativo (Claude). SOLO enums/booleanos/categorías/texto.
-- senales_* son códigos de texto del catálogo por país (no enum rígido).
CREATE TABLE analisis_cualitativos (
    id                            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inmueble_id                   UUID NOT NULL UNIQUE REFERENCES inmuebles(id) ON DELETE CASCADE,
    hash_contenido                TEXT,
    estado_conservacion           estado_conservacion,
    nivel_reforma_estimado        nivel_reforma,
    tipologia                     tipologia_inmueble,
    senales_riesgo                TEXT[] NOT NULL DEFAULT '{}',
    senales_oportunidad           TEXT[] NOT NULL DEFAULT '{}',
    apto_alquiler_larga_estancia  apto_ternario,
    apto_alquiler_turistico       apto_ternario,
    potencial_division_horizontal apto_ternario,
    calidad_descripcion           calidad_descripcion,
    coherencia_precio_descripcion coherencia_precio,
    resumen_analista              TEXT,
    banderas_rojas_texto          TEXT[] NOT NULL DEFAULT '{}',
    nivel_confianza               nivel_confianza,
    campos_no_inferibles          TEXT[] NOT NULL DEFAULT '{}',
    analisis_fallido              BOOLEAN NOT NULL DEFAULT FALSE,
    modelo                        TEXT,
    created_at                    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_analisis_updated
    BEFORE UPDATE ON analisis_cualitativos
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Métricas financieras (motor determinista). En moneda nativa + referencia.
CREATE TABLE metricas_financieras (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    inmueble_id            UUID NOT NULL UNIQUE REFERENCES inmuebles(id) ON DELETE CASCADE,
    version_motor          TEXT NOT NULL,
    moneda                 CHAR(3),          -- moneda nativa de las métricas
    moneda_referencia      CHAR(3),
    tasa_cambio_usada      NUMERIC(18,8),
    conversion_parcial     BOOLEAN NOT NULL DEFAULT FALSE,  -- sin tasa → PARCIAL
    snapshot_supuestos     JSONB NOT NULL,
    snapshot_mercado_pais  JSONB,            -- tipo_interes, ltv_max usados
    snapshot_gastos        JSONB,
    snapshot_coste_reforma JSONB,
    metricas               JSONB NOT NULL,   -- en moneda nativa
    metricas_referencia    JSONB,            -- convertidas a moneda de referencia
    inputs_auditoria       JSONB NOT NULL,   -- cada cifra con su fórmula e inputs
    estado_calidad         calidad_dato NOT NULL,
    campos_faltantes       TEXT[] NOT NULL DEFAULT '{}',
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_metricas_updated
    BEFORE UPDATE ON metricas_financieras
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Scores. Guarda score_bruto (sin riesgo país) y score_total (con multiplicador),
-- para la salvaguarda del toggle "sin riesgo país".
CREATE TABLE scores (
    inmueble_id                    UUID NOT NULL REFERENCES inmuebles(id) ON DELETE CASCADE,
    perfil_id                      UUID NOT NULL REFERENCES perfiles_inversor(id) ON DELETE CASCADE,
    score_bruto                    NUMERIC(6,2),   -- antes del multiplicador de riesgo país
    score_total                    NUMERIC(6,2),   -- después: bruto * (1 - riesgo_pais)
    riesgo_pais_aplicado           NUMERIC(4,3),
    desglose                       JSONB NOT NULL DEFAULT '{}'::jsonb,
    estado_calidad                 calidad_dato NOT NULL,
    motivo_descarte                TEXT[] NOT NULL DEFAULT '{}',   -- riesgos eliminatorios
    usa_parametros_provisionales   BOOLEAN NOT NULL DEFAULT FALSE,
    obsoleto                       BOOLEAN NOT NULL DEFAULT FALSE,
    version_pesos                  TEXT,
    calculado_en                   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (inmueble_id, perfil_id)
);

CREATE INDEX ix_scores_ranking ON scores (perfil_id, score_total DESC);
CREATE INDEX ix_scores_obsoleto ON scores (perfil_id) WHERE obsoleto;
