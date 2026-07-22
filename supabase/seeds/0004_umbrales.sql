-- =============================================================================
-- SEED  Umbrales por (perfil, país)
-- =============================================================================
-- score_descarte = 30 en los tres países (VALIDADO). roi_neto_minimo y
-- descuento_minimo_interes PROVISIONALES (valores de arranque sin fuente).

WITH cf AS (SELECT id FROM perfiles_inversor WHERE nombre = 'CASHFLOW_CORTO_PLAZO'),
     pl AS (SELECT id FROM perfiles_inversor WHERE nombre = 'PLUSVALIA_LARGO_PLAZO')
INSERT INTO umbrales_perfil_pais
    (perfil_id, pais, score_descarte, score_descarte_estado,
     roi_neto_minimo, roi_neto_minimo_estado,
     descuento_minimo_interes, descuento_minimo_estado)
VALUES
    -- CASHFLOW
    ((SELECT id FROM cf), 'ES', 30, 'VALIDADO', 0.05, 'PROVISIONAL', NULL, 'PROVISIONAL'),
    ((SELECT id FROM cf), 'DO', 30, 'VALIDADO', 0.09, 'PROVISIONAL', NULL, 'PROVISIONAL'),
    ((SELECT id FROM cf), 'VE', 30, 'VALIDADO', 0.12, 'PROVISIONAL', NULL, 'PROVISIONAL'),
    -- PLUSVALIA
    ((SELECT id FROM pl), 'ES', 30, 'VALIDADO', 0.03, 'PROVISIONAL', 0.10, 'PROVISIONAL'),
    ((SELECT id FROM pl), 'DO', 30, 'VALIDADO', 0.06, 'PROVISIONAL', 0.15, 'PROVISIONAL'),
    ((SELECT id FROM pl), 'VE', 30, 'VALIDADO', 0.09, 'PROVISIONAL', 0.20, 'PROVISIONAL')
ON CONFLICT (perfil_id, pais) DO NOTHING;
