-- =============================================================================
-- 0006  Señales fuera de catálogo (endurecimiento del cruce con el catálogo)
-- =============================================================================
-- Códigos de señal que Claude devolvió pero el catálogo del país NO contempla.
-- El sistema los separa aquí al validar la salida del analista, en vez de
-- ignorarlos en silencio: así son visibles en la ficha y el monitor.

ALTER TABLE analisis_cualitativos
    ADD COLUMN IF NOT EXISTS senales_no_reconocidas TEXT[] NOT NULL DEFAULT '{}';
