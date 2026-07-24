-- =============================================================================
-- 0009  Contabilidad de tokens y coste: libro de uso + precios configurables
-- =============================================================================
-- El gasto real era invisible. Motivos, los tres:
--
--   1) Los precios estaban HARDCODEADOS en pipeline.py ($3 entrada / $15 salida),
--      que además no son los vigentes (Sonnet 5 está a $2/$10 en precio
--      introductorio). El coste mostrado sobreestimaba el analista un 50%.
--   2) No se contabilizaban los tokens de CACHÉ. La escritura de caché cuesta
--      1.25x la entrada y es justo lo que dispara el gasto de un agente.
--   3) OpenClaw no reportaba NADA: todo su consumo (el grande) era invisible.
--
-- Este esquema arregla los tres: un libro de uso por evento, con las cuatro
-- clases de token y su fuente, y una tabla de precios editable (Principio 2:
-- los precios cambian y son dato, no código).

-- --- Fuente del gasto --------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'fuente_uso') THEN
        -- ANALISTA: llamadas del backend a la API (juicio cualitativo).
        -- OPENCLAW: consumo del agente de extraccion, reportado por el adaptador.
        CREATE TYPE fuente_uso AS ENUM ('ANALISTA', 'OPENCLAW');
    END IF;
END $$;

-- --- Precios por modelo (USD por millón de tokens) ---------------------------
-- Cuatro columnas porque hay cuatro precios distintos, no uno. La escritura de
-- caché a 1.25x y la lectura a 0.1x son las que explican el comportamiento de
-- coste de un agente conversacional.
CREATE TABLE IF NOT EXISTS precios_modelo (
    modelo                TEXT PRIMARY KEY,
    usd_entrada_por_m     NUMERIC(10,4) NOT NULL,
    usd_salida_por_m      NUMERIC(10,4) NOT NULL,
    usd_cache_write_por_m NUMERIC(10,4) NOT NULL,
    usd_cache_read_por_m  NUMERIC(10,4) NOT NULL,
    fuente                TEXT,
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE precios_modelo IS
    'Precios USD/millón por modelo y clase de token. Editables: los precios cambian.';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_precios_modelo_updated') THEN
        CREATE TRIGGER trg_precios_modelo_updated
            BEFORE UPDATE ON precios_modelo
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    END IF;
END $$;

-- Precios vigentes a 2026-07-24 (docs oficiales de Anthropic).
-- OJO Sonnet 5: $2/$10 es PRECIO INTRODUCTORIO hasta el 31-ago-2026; a partir
-- del 1-sep-2026 pasa a $3/$15 (y la caché a 3.75/0.30). Hay que actualizarlo
-- ese día desde la pantalla de Costes, o el coste se subestimará un 50%.
INSERT INTO precios_modelo
    (modelo, usd_entrada_por_m, usd_salida_por_m, usd_cache_write_por_m, usd_cache_read_por_m, fuente)
VALUES
    ('claude-sonnet-5',   2.00, 10.00, 2.50, 0.20, 'Anthropic 2026-07-24 - INTRODUCTORIO hasta 31-ago-2026, luego 3/15/3.75/0.30'),
    ('claude-haiku-4-5',  1.00,  5.00, 1.25, 0.10, 'Anthropic 2026-07-24'),
    ('claude-opus-4-8',   5.00, 25.00, 6.25, 0.50, 'Anthropic 2026-07-24'),
    ('claude-sonnet-4-6', 3.00, 15.00, 3.75, 0.30, 'Anthropic 2026-07-24')
ON CONFLICT (modelo) DO NOTHING;

-- --- Libro de uso: una fila por llamada facturable ---------------------------
-- Grano de evento, no de agregado: de aquí salen todas las vistas (total, por
-- job, por inmueble, por día, por fuente) sin tener que decidirlas ahora.
CREATE TABLE IF NOT EXISTS uso_tokens (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fuente              fuente_uso NOT NULL,
    modelo              TEXT,
    job_id              UUID REFERENCES jobs(id) ON DELETE SET NULL,
    inmueble_id         UUID REFERENCES inmuebles(id) ON DELETE SET NULL,
    tokens_entrada      INT NOT NULL DEFAULT 0,
    tokens_salida       INT NOT NULL DEFAULT 0,
    tokens_cache_write  INT NOT NULL DEFAULT 0,
    tokens_cache_read   INT NOT NULL DEFAULT 0,
    -- Coste congelado en el momento del gasto: si mañana cambian los precios,
    -- el histórico no se reescribe solo. Es contabilidad, no una proyección.
    coste_usd           NUMERIC(12,6) NOT NULL DEFAULT 0,
    detalle             JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE uso_tokens IS
    'Libro de gasto por evento. Cuatro clases de token + coste congelado al precio del momento.';

CREATE INDEX IF NOT EXISTS ix_uso_tokens_fecha  ON uso_tokens (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_uso_tokens_job    ON uso_tokens (job_id);
CREATE INDEX IF NOT EXISTS ix_uso_tokens_inm    ON uso_tokens (inmueble_id);
CREATE INDEX IF NOT EXISTS ix_uso_tokens_fuente ON uso_tokens (fuente, created_at DESC);

-- --- Umbral de aviso de gasto ------------------------------------------------
-- Solo AVISA (Parte 1). Un tope que además CORTE la ejecución es la Parte 2 y
-- no se implementa sin aprobación explícita.
INSERT INTO config_app (clave, valor) VALUES
    ('umbral_gasto_diario_usd', '1.00'),
    ('umbral_gasto_total_usd', '25.00')
ON CONFLICT (clave) DO NOTHING;
