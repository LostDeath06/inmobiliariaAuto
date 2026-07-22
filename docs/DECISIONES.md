# Registro de decisiones

Decisiones de negocio, alcance y arquitectura tomadas explícitamente por el
propietario. Este archivo es autoritativo: si el código y este registro
discrepan, gana este registro (y hay que corregir el código).

## Cadencia de trabajo

- Construcción en silencio, sin narrar progreso ni pedir confirmación por fase.
- El asistente solo interrumpe si necesita una **decisión** o un **dato** que no tiene.
- **Línea roja #3 intacta:** no se inventan datos. Dato ausente → el inmueble sale
  `NO_CALCULABLE` y el sistema dice exactamente qué falta. Ningún país arranca
  hasta que se carguen sus datos (España incluida). Es el comportamiento correcto.

## Alcance: MULTI-PAÍS desde el día uno

España (ES), República Dominicana (DO) y Venezuela (VE). Estructural, no cosmético.
Anula la decisión previa "5A / España primero".

### Divisa
- El esquema de OpenClaw e `inmuebles` usan `precio` + `moneda` (ISO 4217), no `precio_eur`.
- Métricas calculadas en **moneda nativa**; se muestran además en `moneda_referencia`
  (configurable, `config_app`, por defecto EUR).
- `tipos_cambio` en BD (origen, destino, tasa, fuente, fecha). Convierte **Python**,
  nunca Claude, nunca hardcodeado. **Carga manual desde la UI, sin feeds.**
  Sin tasa → conversión a referencia `PARCIAL`, jamás una tasa inventada.

### Configuración por eje
| Vive por… | Contiene |
|---|---|
| Perfil | `pesos` (aprobados), `supuestos` = {ltv, plazo_anos, vacancia_pct, gastos_gestion_pct} |
| País (`config_mercado_pais`) | `tipo_interes_anual`, `ltv_max`, `riesgo_pais`, saturaciones de normalización, monedas |
| (Perfil × País) (`umbrales_perfil_pais`) | `score_descarte`, `roi_neto_minimo`, `descuento_minimo_interes` |

### Scoring
- **Pesos** (VALIDADO): CASHFLOW 40/15/5/5/15/10/10 · PLUSVALIA 10/25/25/20/5/10/5
  (rentabilidad_neta, descuento_mercado, calidad_zona, margen_reforma, aptitud_alquiler,
  riesgo_activo, oportunidad_temporal).
- `riesgo_activo` **partido**: eliminatorios (descarte duro → estado `DESCARTADO_RIESGO`,
  fuera del ranking, no se ponderan) vs. ponderables (penalización, sí ponderan).
  Catálogo de riesgos **en BD** (no enum rígido), por país (`catalogo_riesgos`, `riesgos_pais`).
- Mapa de penalización ponderable **ES (VALIDADO)**: CARGAS −50 · PROINDIVISO −40 ·
  RUINA −40 · ALQUILADO_RENTA_ANTIGUA −35 · SUBASTA −30 · SIN_CEDULA −25 · A_REFORMAR −10.
  Eliminatorios ES (VALIDADO): OKUPAS, DERRIBO.
- `oportunidad_temporal` con <2 puntos de histórico y sin señal cualitativa =
  **NO_CALCULABLE** (redistribuye peso vía `PARCIAL`), no 0.
- `riesgo_pais` entra como **multiplicador**: `score_final = score_bruto × (1 − riesgo_pais)`.
  Se guardan ambos (bruto y final) para la salvaguarda del toggle.
- `tipo_interes_anual` es **dato de mercado por país**, no preferencia del perfil.
- VE **al contado**: `ltv_max = 0` (VALIDADO, limitación real del mercado).

### Umbrales / parámetros
- `score_descarte` = **30 en los tres países** (VALIDADO). No se sube por país:
  subirlo además del `riesgo_pais` penalizaría dos veces y vaciaría VE.
- ES `tipo_interes_anual` = **3.5%** (VALIDADO). DO = **NULL** (pendiente). VE = al contado.

### Parámetros PROVISIONALES (arranque, no validados)
Cada uno lleva flag `PROVISIONAL | VALIDADO` en BD; la UI avisa visiblemente cuando
un score se calcula con parámetros provisionales.
- `riesgo_pais`: ES 0.00 · DO 0.12 · VE 0.25
- `roi_neto_minimo`: cashflow 5/9/12 · plusvalía 3/6/9 (ES/DO/VE)
- Saturación `rentabilidad_neta`: ES 7% · DO 12% · VE 15%
- Saturación `descuento_mercado`: 30% / 35% / 40%

### Datos PENDIENTES (no inventar, no bloquear)
- Gastos de adquisición de ES, DO y VE (todos).
- Riesgos eliminatorios y ponderables de DO y VE.
- `tipo_interes_anual` de DO (queda `NULL`).
Resolución: tablas creadas, vacías, editables desde la UI. Falta un dato →
`NO_CALCULABLE` con detalle de qué falta. Pantalla "Estado de configuración por país"
(checklist de operatividad). Datos ficticios de tests/demo marcados como tales,
nunca mezclados con configuración real.

### Salvaguardas del ranking
- Filtro por país (Top-N dentro de un país, no solo global).
- Toggle "sin riesgo país" (ver `score_bruto`, sin el multiplicador).

### Decisiones técnicas previas que siguen en pie
- 2A cuarentena de anuncios inválidos (consultable en monitor de jobs).
- 3A bandera de posible duplicado cross-portal visible en el ranking.
- 4A mono-usuario auto-hospedado, esquema preparado para multi-tenant.
- 6A test anti-hardcode acotado a `backend/dominio/`.
- 7A worker con APScheduler, sin Redis ni Celery.
- 8B modelo `claude-sonnet-5`.
- Puerto docker-compose: **5455**.

### Señales fuera del catálogo del país (endurecimiento)
`senales_riesgo` / `senales_oportunidad` son `list[str]` (el catálogo vive en BD y varía
por país, así que no pueden ser un enum). Antes, un código que Claude devolviera fuera
de catálogo pasaba la validación de Pydantic y luego no cruzaba con nada en el scoring:
ni descarte duro ni penalización. Se ignoraba en silencio — un riesgo real podía quedar
sin efecto en el score sin que nadie lo viera.

Resolución: al procesar la salida de Claude, `validar_senales()` (en
`servicios/analista_cualitativo.py`, función pura) cruza cada código contra el catálogo
del país:
- Código en catálogo → se conserva en su lista y surte efecto normal.
- Código fuera de catálogo → **no se descarta en silencio**: se separa a
  `senales_no_reconocidas` (columna nueva, migración `0006`), visible en la ficha del
  inmueble (aviso) y en el monitor (`GET /api/senales-no-reconocidas`).
- `NINGUNA` se trata como sentinela de "sin señal": ni se aplica ni se marca.

Un código ahí significa una de dos cosas, ambas accionables: o Claude alucina un código,
o falta ese código en el catálogo de ese país. Para DO/VE (con `riesgos_pais` aún vacío)
todo código emitido cae en `senales_no_reconocidas`, que es el aviso correcto.

Protegido por `tests/servicios/test_senales_no_reconocidas.py` (8 tests).

### Blindaje: el fallo silencioso empuja al alza
Consecuencia de validar contra `riesgos_pais` (y no contra el catálogo global): un país
sin catálogo configurado —hoy DO y VE— deja TODAS las señales de riesgo en
`senales_no_reconocidas`, así que ninguna cruza: ni los eliminatorios. Un inmueble con
OKUPAS en RD entraría al ranking sin descartar ni penalizar.

Esto es configuración que falta, no un bug: no se "arregla" inventando un catálogo. Pero
es silencioso y, peor, **sesga al alza**: `riesgo_activo` sin penalizaciones normaliza al
máximo (100 puntos = "sin riesgo alguno"). El error empuja justo en la dirección
peligrosa para quien decide comprar. Dos blindajes para que sea imposible de ignorar:

1. **Estado por país**: un país con `riesgos_pais` vacío muestra advertencia explícita
   ("ninguna señal de riesgo se aplicará al score… pueden estar infra-penalizados") y el
   país se marca *Calibración incompleta*, no el genérico *Faltan datos*.
2. **Scoring**: `ajustar_por_senales_ignoradas()` (función pura) impide que un score con
   señales ignoradas se presente como COMPLETO — lo degrada a PARCIAL y guarda los
   códigos en `desglose`. El ranking lo marca con `SEÑAL IGNORADA` y la ficha lo explica.

Aplica también a ES, no solo a DO/VE: si Claude devuelve un código que el catálogo de ES
no contempla, la penalización sale 0 y el score salía COMPLETO. Ese era el caso real que
destapó el blindaje.

Protegido por `tests/servicios/test_blindaje_senales_ignoradas.py` (6 tests).
