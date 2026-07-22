-- =============================================================================
-- SEED  Perfiles de inversor  (pesos APROBADOS en la Fase 2)
-- =============================================================================
-- Pesos y supuestos aprobados por el propietario. `ltv` es la preferencia del
-- inversor; el tope real por país (VE = al contado) se aplica vía
-- config_mercado_pais.ltv_max.

INSERT INTO perfiles_inversor (nombre, descripcion, es_predeterminado, pesos, supuestos)
VALUES
    (
        'CASHFLOW_CORTO_PLAZO',
        'Prioriza flujo de caja inmediato, rentabilidad neta y bajo capital inmovilizado.',
        TRUE,
        '{"rentabilidad_neta":0.40,"descuento_mercado":0.15,"calidad_zona":0.05,"margen_reforma":0.05,"aptitud_alquiler":0.15,"riesgo_activo":0.10,"oportunidad_temporal":0.10}'::jsonb,
        '{"ltv":0.70,"plazo_anos":25,"vacancia_pct":0.05,"gastos_gestion_pct":0.08}'::jsonb
    ),
    (
        'PLUSVALIA_LARGO_PLAZO',
        'Prioriza revalorización, calidad de zona, potencial de mejora y entrada por debajo de mercado.',
        FALSE,
        '{"rentabilidad_neta":0.10,"descuento_mercado":0.25,"calidad_zona":0.25,"margen_reforma":0.20,"aptitud_alquiler":0.05,"riesgo_activo":0.10,"oportunidad_temporal":0.05}'::jsonb,
        '{"ltv":0.70,"plazo_anos":30,"vacancia_pct":0.05,"gastos_gestion_pct":0.08}'::jsonb
    )
ON CONFLICT (nombre) DO NOTHING;
