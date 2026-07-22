-- =============================================================================
-- 0002  Enumeraciones
-- =============================================================================
-- Los valores de negocio (pesos, umbrales, costes) NO son enums: viven en BD
-- como datos editables. Estos enums son categorías estructurales cerradas.

CREATE TYPE nivel_reforma AS ENUM (
    'NINGUNA', 'COSMETICA', 'MEDIA', 'INTEGRAL', 'DESCONOCIDO'
);

CREATE TYPE estado_job AS ENUM (
    'PENDIENTE', 'ENVIADO', 'EN_PROGRESO',
    'COMPLETADO', 'PARCIAL', 'FALLIDO', 'CANCELADO'
);

CREATE TYPE tipo_gasto_adquisicion AS ENUM ('PORCENTAJE', 'FIJO');

CREATE TYPE estado_conservacion AS ENUM (
    'OBRA_NUEVA', 'REFORMADO', 'BUEN_ESTADO', 'A_REFORMAR', 'RUINA', 'DESCONOCIDO'
);

CREATE TYPE tipologia_inmueble AS ENUM (
    'PISO', 'ATICO', 'BAJO', 'DUPLEX', 'CASA', 'CHALET', 'LOCAL', 'SOLAR', 'OTRO'
);

CREATE TYPE apto_ternario AS ENUM ('SI', 'NO', 'DUDOSO');

CREATE TYPE calidad_descripcion AS ENUM (
    'DETALLADA', 'ESTANDAR', 'POBRE', 'ENGANOSA'
);

CREATE TYPE coherencia_precio AS ENUM (
    'COHERENTE', 'SOSPECHOSAMENTE_BAJO', 'SOBREVALORADO', 'NO_EVALUABLE'
);

CREATE TYPE nivel_confianza AS ENUM ('ALTA', 'MEDIA', 'BAJA');

CREATE TYPE tipo_anunciante AS ENUM (
    'PARTICULAR', 'AGENCIA', 'PROMOTOR', 'DESCONOCIDO'
);

-- Estado de calidad / disposición del inmueble y del score.
-- DESCARTADO_RIESGO: excluido del ranking por un riesgo eliminatorio, sin
-- importar el score (no se pondera).
CREATE TYPE calidad_dato AS ENUM (
    'COMPLETO', 'PARCIAL', 'NO_CALCULABLE', 'DESCARTADO_RIESGO'
);

-- Estado de validación de un parámetro de negocio provisional.
CREATE TYPE estado_parametro AS ENUM ('PROVISIONAL', 'VALIDADO');

-- Clase de una señal del catálogo de riesgos/oportunidades.
CREATE TYPE clase_senal AS ENUM ('RIESGO', 'OPORTUNIDAD');
