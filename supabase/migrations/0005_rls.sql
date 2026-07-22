-- =============================================================================
-- 0005  Row Level Security
-- =============================================================================
-- Decisión 4A: mono-usuario auto-hospedado. RLS ACTIVADO en todas las tablas con
-- política PERMISIVA. Migrar a multi-tenant = sustituir estas políticas por otras
-- basadas en el usuario autenticado, sin cambios de esquema.

DO $$
DECLARE
    t TEXT;
    tablas TEXT[] := ARRAY[
        'paises', 'config_app', 'perfiles_inversor', 'config_mercado_pais',
        'umbrales_perfil_pais', 'tipos_cambio', 'catalogo_riesgos', 'riesgos_pais',
        'costes_reforma', 'gastos_adquisicion', 'benchmarks_zona', 'portales',
        'busquedas', 'jobs', 'anuncios_crudos', 'anuncios_cuarentena', 'inmuebles',
        'historico_precios', 'analisis_cualitativos', 'metricas_financieras', 'scores'
    ];
BEGIN
    FOREACH t IN ARRAY tablas LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY;', t);
        EXECUTE format(
            'CREATE POLICY %I ON %I FOR ALL USING (true) WITH CHECK (true);',
            'permisiva_' || t, t
        );
    END LOOP;
END $$;
