-- =============================================================================
-- 0008  CONFOTUR (Ley 158-01, República Dominicana) + regiones fiscales
-- =============================================================================
-- Dos cosas que el modelo no contemplaba y que cambian el CÁLCULO, no solo la
-- presentación:
--
-- 1) CONFOTUR. Un proyecto acogido a la Ley 158-01 está exento del impuesto de
--    transferencia (3%) y del IPI durante 15 años. Dos inmuebles idénticos, uno
--    con CONFOTUR y otro sin él, tienen gastos de adquisición muy distintos.
--    Aplicar el 3% a todos infla el coste de los exentos y hunde su ROI.
--
--    QUÉ concepto queda exento es DATO, no código (Principio 2): lo marca la
--    columna `exento_confotur` de gastos_adquisicion. El motor no sabe qué es un
--    impuesto de transferencia; solo salta los gastos marcados.
--
--    `tiene_confotur` es NULL por defecto = DESCONOCIDO, que NO es lo mismo que
--    "no tiene". Un desconocido con exenciones configuradas degrada la calidad
--    del dato a PARCIAL en vez de asumir en silencio que paga el impuesto.
--
-- 2) Regiones fiscales. El ITP español varía por comunidad autónoma, así que
--    gastos_adquisicion se llena con una fila por comunidad. Pero el inmueble
--    solo trae `provincia`: hace falta un mapa provincia -> comunidad para saber
--    qué fila le toca. Ese mapa es dato (lo carga el script de configuración),
--    no un diccionario en Python.

-- --- 1. CONFOTUR a nivel de inmueble ----------------------------------------
ALTER TABLE inmuebles
    -- NULL = desconocido · TRUE = acogido a Ley 158-01 · FALSE = confirmado que no.
    -- Lo fija el propietario desde la ficha. Claude solo puede sugerirlo.
    ADD COLUMN IF NOT EXISTS tiene_confotur BOOLEAN;

COMMENT ON COLUMN inmuebles.tiene_confotur IS
    'Ley 158-01 CONFOTUR (RD). NULL = desconocido, nunca equivale a FALSE.';

-- --- 2. Qué gastos exime CONFOTUR (configurable, no hardcodeado) ------------
ALTER TABLE gastos_adquisicion
    ADD COLUMN IF NOT EXISTS exento_confotur BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN gastos_adquisicion.exento_confotur IS
    'TRUE si este concepto no se paga cuando el inmueble está acogido a CONFOTUR.';

-- --- 3. Señal cualitativa de Claude -----------------------------------------
-- SOLO juicio: "¿el anuncio menciona CONFOTUR / Ley 158-01 / exención fiscal?".
-- No decide nada: la decisión de aplicar la exención la toma Python leyendo
-- inmuebles.tiene_confotur, que fija el propietario. Ternario: SI / NO / DUDOSO,
-- y NULL si el análisis no existe.
ALTER TABLE analisis_cualitativos
    ADD COLUMN IF NOT EXISTS menciona_exencion_fiscal apto_ternario;

COMMENT ON COLUMN analisis_cualitativos.menciona_exencion_fiscal IS
    'Señal cualitativa: el anuncio menciona CONFOTUR/Ley 158-01/exención. Sugerencia, no decisión.';

-- --- 3bis. Por qué falló un análisis ----------------------------------------
-- El analista atrapaba toda excepción y seguía, así que un análisis fallido no
-- dejaba rastro del motivo: el job salía con coste 0.0000 y nadie sabía si era
-- la clave de la API, el modelo o la red. Un fallo silencioso es peor que uno
-- ruidoso (principio 3): a partir de ahora el motivo se guarda.
ALTER TABLE analisis_cualitativos
    ADD COLUMN IF NOT EXISTS motivo_fallo TEXT;

COMMENT ON COLUMN analisis_cualitativos.motivo_fallo IS
    'Última excepción del analista cuando analisis_fallido = TRUE. NULL si fue bien.';

-- --- 4. Mapa provincia -> región fiscal --------------------------------------
-- Sin esto, un inmueble de Valencia (provincia) no encuentra la fila de ITP de
-- "Comunidad Valenciana" y el motor sumaría TODAS las comunidades, o ninguna.
CREATE TABLE IF NOT EXISTS regiones_fiscales (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pais       CHAR(2) NOT NULL REFERENCES paises(codigo),
    provincia  TEXT NOT NULL,
    region     TEXT NOT NULL,
    fuente     TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (pais, provincia)
);

COMMENT ON TABLE regiones_fiscales IS
    'Mapa provincia -> región fiscal (p. ej. Valencia -> Comunidad Valenciana) para elegir el gasto de adquisición que aplica.';

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trg_regiones_fiscales_updated'
    ) THEN
        CREATE TRIGGER trg_regiones_fiscales_updated
            BEFORE UPDATE ON regiones_fiscales
            FOR EACH ROW EXECUTE FUNCTION set_updated_at();
    END IF;
END $$;
