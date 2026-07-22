-- =============================================================================
-- SEED  Países y configuración global
-- =============================================================================
INSERT INTO paises (codigo, nombre) VALUES
    ('ES', 'España'),
    ('DO', 'República Dominicana'),
    ('VE', 'Venezuela')
ON CONFLICT (codigo) DO NOTHING;

-- Moneda de referencia para mostrar métricas (configurable desde la UI).
INSERT INTO config_app (clave, valor) VALUES
    ('moneda_referencia', 'EUR')
ON CONFLICT (clave) DO NOTHING;

-- Esqueleto de costes de reforma por país y nivel. coste_m2 = NULL (dato ausente,
-- nunca inventado). La UI marca los huecos; sin el dato, el inmueble sale
-- NO_CALCULABLE para el coste de reforma.
INSERT INTO costes_reforma (pais, nivel_reforma, coste_m2, moneda) VALUES
    ('ES', 'NINGUNA', NULL, 'EUR'), ('ES', 'COSMETICA', NULL, 'EUR'),
    ('ES', 'MEDIA', NULL, 'EUR'),   ('ES', 'INTEGRAL', NULL, 'EUR'),
    ('DO', 'NINGUNA', NULL, 'USD'), ('DO', 'COSMETICA', NULL, 'USD'),
    ('DO', 'MEDIA', NULL, 'USD'),   ('DO', 'INTEGRAL', NULL, 'USD'),
    ('VE', 'NINGUNA', NULL, 'USD'), ('VE', 'COSMETICA', NULL, 'USD'),
    ('VE', 'MEDIA', NULL, 'USD'),   ('VE', 'INTEGRAL', NULL, 'USD')
ON CONFLICT (pais, nivel_reforma) DO NOTHING;
