-- =============================================================================
-- 0001  Extensiones y utilidades comunes
-- =============================================================================

-- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Función de utilidad: mantiene actualizado `updated_at` en cada UPDATE.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Función de utilidad: bloquea UPDATE y DELETE en tablas inmutables
-- (append-only). Se usa en `anuncios_crudos`, la única fuente de verdad
-- auditable del sistema.
CREATE OR REPLACE FUNCTION prohibir_modificacion()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Tabla inmutable (append-only): no se permite % en %',
        TG_OP, TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;
