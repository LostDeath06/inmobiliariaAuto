-- =============================================================================
-- 0011  Cancelar de verdad, matar zombis y ver el gasto de las conversaciones
-- =============================================================================
-- Tres agujeros que salieron a la vez, todos del mismo tipo: el sistema decía
-- una cosa y la realidad hacía otra.
--
--   1) CANCELAR no cancelaba. El adaptador cambiaba una etiqueta en memoria y
--      el proceso `openclaw agent` seguía vivo gastando tokens. La app decía
--      "CANCELADO" mientras el saldo bajaba: peor que no tener botón.
--   2) Un job podía quedarse EN_PROGRESO PARA SIEMPRE. Al reiniciar el
--      adaptador, este perdía su memoria y respondía 404; el backend seguía
--      sondeándolo cada 3 s indefinidamente. Nada le ponía fecha límite.
--   3) El libro de gasto solo veía el trabajo del sistema. Hablar con el agente
--      por terminal o Telegram cuesta igual —y más, porque una sesión larga
--      reescribe su historial entero en cada mensaje— y era invisible.

-- --- 1. Una tercera fuente de gasto -----------------------------------------
-- OPENCLAW pasa a significar "jobs de extracción". Las conversaciones directas
-- son otra cosa y van SEPARADAS: mezclarlas escondería que el gasto de charlar
-- puede superar al de trabajar.
ALTER TYPE fuente_uso ADD VALUE IF NOT EXISTS 'OPENCLAW_CONVERSACION';

-- --- 2. Rendirse ante un adaptador que no reconoce el job --------------------
-- Contador de consultas seguidas contestadas con 404. Vive en BD, no en el
-- worker: el worker también se reinicia, y un contador en memoria volvería a
-- empezar de cero cada vez, que es como no tenerlo.
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS sondeos_no_encontrado INT NOT NULL DEFAULT 0;

COMMENT ON COLUMN jobs.sondeos_no_encontrado IS
    'Consultas seguidas en las que el adaptador respondió 404. Al llegar al '
    'límite el job se cierra FALLIDO: el adaptador perdió su memoria (reinicio).';

-- --- 3. Sesiones de conversación: contabilidad por incremento ----------------
-- El fichero .jsonl de una sesión crece: cada lectura ve el TOTAL acumulado, no
-- lo nuevo. Sin recordar lo ya anotado, cada pasada del worker sumaría otra vez
-- toda la sesión y el gasto se multiplicaría por el número de lecturas.
-- Aquí se guarda la última foto; al libro solo va la DIFERENCIA.
CREATE TABLE IF NOT EXISTS sesiones_openclaw (
    id                       TEXT PRIMARY KEY,   -- clave de sesión o nombre del fichero
    agente                   TEXT,
    modelo                   TEXT,
    -- Última foto contabilizada. La resta contra la lectura nueva es lo que
    -- entra en `uso_tokens`.
    tokens_entrada           BIGINT NOT NULL DEFAULT 0,
    tokens_salida            BIGINT NOT NULL DEFAULT 0,
    tokens_cache_write       BIGINT NOT NULL DEFAULT 0,
    tokens_cache_read        BIGINT NOT NULL DEFAULT 0,
    turnos                   INT    NOT NULL DEFAULT 0,
    -- Lo que costará el PRÓXIMO mensaje de esta sesión. Es la cifra que dispara
    -- el aviso: el acumulado ya está gastado, esto es lo que se puede evitar.
    tokens_proximo_mensaje   INT    NOT NULL DEFAULT 0,
    bytes                    BIGINT NOT NULL DEFAULT 0,
    modificada_en            TIMESTAMPTZ,
    leida_en                 TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE sesiones_openclaw IS
    'Última foto de cada sesión de OpenClaw en disco. Existe para anotar solo el '
    'incremento en uso_tokens y no contar dos veces la misma conversación.';

CREATE INDEX IF NOT EXISTS ix_sesiones_openclaw_prox
    ON sesiones_openclaw (tokens_proximo_mensaje DESC);

-- --- 4. Parámetros nuevos (dato en BD, no en Python — Principio 2) -----------
INSERT INTO config_app (clave, valor) VALUES
    -- Consultas 404 seguidas que se toleran antes de dar el job por perdido.
    -- Con el sondeo cada 15 s, 5 son ~75 s: suficiente para un reinicio normal
    -- del adaptador, poco para dejar ruido en los logs.
    ('max_sondeos_no_encontrado', '5'),
    -- Margen sobre OPENCLAW_TIMEOUT_SEGUNDOS antes del corte duro. El adaptador
    -- ya se da 60 s de margen sobre el CLI; el backend se da otros 120 para no
    -- matar un job que está terminando de reportar.
    ('margen_timeout_job_segundos', '120'),
    -- Aviso de sesión que engorda. 50.000 tokens por mensaje a $2,50/millón de
    -- escritura de caché son ~$0,125 CADA VEZ que escribes.
    ('umbral_tokens_sesion', '50000')
ON CONFLICT (clave) DO NOTHING;
