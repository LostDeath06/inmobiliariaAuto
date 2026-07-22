-- =============================================================================
-- SEED  Configuración de mercado por país
-- =============================================================================
-- VALIDADO: ES tipo_interes 3.5%, VE al contado (ltv_max=0), score_descarte 30.
-- PROVISIONAL: riesgo_pais, saturaciones (valores de arranque sin fuente).
-- PENDIENTE (NULL): tipo_interes de DO.

INSERT INTO config_mercado_pais
    (pais, monedas_nativas, tipo_interes_anual, tipo_interes_estado,
     ltv_max, ltv_max_estado, riesgo_pais, riesgo_pais_estado,
     sat_rentabilidad_neta, sat_rentabilidad_estado,
     sat_descuento_mercado, sat_descuento_estado)
VALUES
    ('ES', ARRAY['EUR'], 0.0350, 'VALIDADO',
     NULL, 'VALIDADO', 0.000, 'PROVISIONAL',
     0.0700, 'PROVISIONAL', 0.3000, 'PROVISIONAL'),
    ('DO', ARRAY['DOP','USD'], NULL, 'PROVISIONAL',
     NULL, 'PROVISIONAL', 0.120, 'PROVISIONAL',
     0.1200, 'PROVISIONAL', 0.3500, 'PROVISIONAL'),
    ('VE', ARRAY['USD'], NULL, 'VALIDADO',
     0.000, 'VALIDADO', 0.250, 'PROVISIONAL',
     0.1500, 'PROVISIONAL', 0.4000, 'PROVISIONAL')
ON CONFLICT (pais) DO NOTHING;

-- Catálogo de riesgos/oportunidades (menú editable; la aplicación por país va
-- en riesgos_pais). Incluye señales ES y candidatas neutrales para DO/VE.
INSERT INTO catalogo_riesgos (codigo, clase, descripcion) VALUES
    ('OKUPAS', 'RIESGO', 'Ocupación ilegal del inmueble'),
    ('DERRIBO', 'RIESGO', 'Orden o riesgo de derribo'),
    ('CARGAS', 'RIESGO', 'Cargas, embargos o hipotecas pendientes'),
    ('PROINDIVISO', 'RIESGO', 'Propiedad compartida / proindiviso'),
    ('SUBASTA', 'RIESGO', 'Inmueble en subasta'),
    ('SIN_CEDULA', 'RIESGO', 'Sin cédula de habitabilidad'),
    ('ALQUILADO_RENTA_ANTIGUA', 'RIESGO', 'Alquilado con renta antigua'),
    ('ESTADO_RUINA', 'RIESGO', 'Estado de conservación en ruina'),
    ('ESTADO_A_REFORMAR', 'RIESGO', 'Estado a reformar'),
    ('OCUPACION_INFORMAL', 'RIESGO', 'Ocupación informal / invasión (candidata DO/VE)'),
    ('SIN_TITULO_CLARO', 'RIESGO', 'Título de propiedad poco claro (candidata DO/VE)'),
    ('RIESGO_EXPROPIACION', 'RIESGO', 'Riesgo de expropiación (candidata DO/VE)'),
    ('LITIGIO_JUDICIAL', 'RIESGO', 'Litigio judicial en curso (candidata DO/VE)'),
    ('VENTA_URGENTE', 'OPORTUNIDAD', 'El vendedor tiene urgencia'),
    ('HERENCIA', 'OPORTUNIDAD', 'Procedente de herencia'),
    ('PRECIO_REBAJADO', 'OPORTUNIDAD', 'Precio recientemente rebajado'),
    ('PARTICULAR_SIN_AGENCIA', 'OPORTUNIDAD', 'Vende un particular sin agencia'),
    ('REFORMABLE_CON_MARGEN', 'OPORTUNIDAD', 'Reformable con margen de valor')
ON CONFLICT (codigo) DO NOTHING;

-- Aplicación por país. SOLO ES (aprobado). DO y VE quedan VACÍOS: hasta que el
-- propietario los cargue, esos países no descartan por riesgo y su componente
-- riesgo_activo saldrá NO_CALCULABLE (peso redistribuido).
--   Eliminatorios ES: OKUPAS, DERRIBO.
--   Ponderables ES (mapa aprobado).
INSERT INTO riesgos_pais (pais, codigo, es_eliminatorio, penalizacion) VALUES
    ('ES', 'OKUPAS', TRUE, NULL),
    ('ES', 'DERRIBO', TRUE, NULL),
    ('ES', 'CARGAS', FALSE, -50),
    ('ES', 'PROINDIVISO', FALSE, -40),
    ('ES', 'ESTADO_RUINA', FALSE, -40),
    ('ES', 'ALQUILADO_RENTA_ANTIGUA', FALSE, -35),
    ('ES', 'SUBASTA', FALSE, -30),
    ('ES', 'SIN_CEDULA', FALSE, -25),
    ('ES', 'ESTADO_A_REFORMAR', FALSE, -10)
ON CONFLICT (pais, codigo) DO NOTHING;
