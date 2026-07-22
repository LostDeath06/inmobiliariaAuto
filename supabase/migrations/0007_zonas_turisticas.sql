-- =============================================================================
-- 0007  Zonas de perfil turístico + benchmark de alquiler de corta estancia
-- =============================================================================
-- Prepara el terreno para zonas como Cap Cana, donde la inversión es de plusvalía
-- y alquiler de CORTA estancia (turístico), no cashflow de larga estancia. El motor
-- de cashflow no se toca; estos campos quedan para cuando el propietario cargue
-- datos reales de ADR y ocupación. NADA se calcula ni se rellena aquí.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'perfil_zona') THEN
        CREATE TYPE perfil_zona AS ENUM ('ESTANDAR', 'TURISTICA');
    END IF;
END $$;

ALTER TABLE benchmarks_zona
    -- Marca la zona: ESTANDAR (larga estancia) o TURISTICA (plusvalía / corta estancia).
    ADD COLUMN IF NOT EXISTS perfil_zona perfil_zona NOT NULL DEFAULT 'ESTANDAR',
    -- Modalidad de alquiler de CORTA estancia (turístico). Se cargan a mano; NULL = ausente.
    ADD COLUMN IF NOT EXISTS adr_medio                NUMERIC(12,2),  -- tarifa media por noche, moneda de la zona
    ADD COLUMN IF NOT EXISTS ocupacion_media          NUMERIC(4,3),   -- 0..1 (p. ej. 0.70 = 70%)
    ADD COLUMN IF NOT EXISTS gastos_gestion_corta_pct NUMERIC(4,3);   -- gestión de corta estancia (mayor que la larga)
