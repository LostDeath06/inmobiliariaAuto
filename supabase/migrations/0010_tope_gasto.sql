-- =============================================================================
-- 0010  Tope de gasto: refuse-to-dispatch
-- =============================================================================
-- Distinto de los umbrales de AVISO de la 0009:
--
--   umbral_gasto_*  -> solo avisa en el dashboard. No cambia el comportamiento.
--   tope_gasto_*    -> CORTA: no se despacha trabajo nuevo por encima de esto.
--
-- El corte es "no empezar", nunca "matar a mitad". Abortar un job en vuelo deja
-- estado parcial y contradice el principio de no abortar el lote; en cambio,
-- negarse a arrancar es limpio y no pierde nada.
--
-- Valor de arranque deliberadamente CONSERVADOR: un job típico de OpenClaw se
-- estimó en ~1,75 USD, así que 2,00 USD/día deja pasar aproximadamente uno.
-- Es para subirlo a conciencia desde la pantalla de Costes, no para quedarse.

INSERT INTO config_app (clave, valor) VALUES
    ('tope_gasto_diario_usd', '2.00')
ON CONFLICT (clave) DO NOTHING;
