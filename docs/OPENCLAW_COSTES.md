# Coste de OpenClaw: podar el preámbulo

> **Por qué.** Una sonda trivial a OpenClaw consumió **19.254 tokens de escritura
> de caché** — el system prompt, 16 skills y 7 ficheros de workspace, todo
> inyectado antes de la primera palabra útil. A $2,50/millón eso son **$0,048 de
> suelo por job**, más caro que analizar tres inmuebles enteros. Con el contrato
> §5.4 que inyecta el adaptador (2.930 tokens) el preámbulo real ronda los
> **22.200 tokens**.
>
> Podarlo es el mayor ahorro disponible (~73%) y **no toca ninguna garantía** del
> sistema: cada job sigue teniendo su sesión limpia.

---

## 1. Medir ANTES (para poder demostrar la mejora)

OpenClaw reporta la composición de su system prompt. Anota estos números:

```bash
openclaw agent --message "responde solo: ok" --json 2>&1 | tee /tmp/antes.json
```

Busca en la salida `systemPromptReport` (caracteres totales, ficheros de
workspace, skills cargadas) y `meta.agentMeta.usage.cacheWrite`.

Punto de partida conocido: **30.803 caracteres**, 7 ficheros de workspace,
16 skills, **19.254 tokens de cacheWrite**.

## 2. Crear un agente dedicado y flaco

Un job de scraping necesita navegar y devolver el JSON del contrato. No necesita
16 skills. En `/root/.openclaw/openclaw.json`:

```json5
{
  agents: {
    entries: {
      "inmobiliaria-scraper": {
        // Lista blanca de skills: [] = ninguna. Si la navegación depende de
        // alguna skill concreta, pon SOLO esa, no el catálogo entero.
        // `agents.entries.*.skills` REEMPLAZA a `agents.defaults.skills`.
        skills: [],
      },
    },
  },
  skills: {
    limits: {
      // Techo duro del bloque de skills en el prompt. Red de seguridad por si
      // mañana se añade una skill nueva a los defaults.
      maxSkillsPromptChars: 2000,
    },
  },
}
```

> **Verificado** contra <https://docs.openclaw.ai/tools/skills>: `agents.defaults.skills`
> y `agents.entries.*.skills` aceptan un array de nombres o `[]` para no exponer
> ninguna; `skills.limits.maxSkillsPromptChars` recorta el bloque si se pasa.
>
> **NO verificado:** cómo se desactiva la inyección de los **7 ficheros de
> workspace**. La documentación consultada no lo cubre, y no voy a inventarme una
> clave de configuración. Mídelo en el paso 4: si tras podar las skills el
> preámbulo sigue alto, los ficheros son el resto. La vía práctica es sacar del
> workspace del agente lo que el scraping no necesita.

## 3. Apuntar el adaptador a ese agente

El adaptador ya soporta elegir agente (`--agent`), así que basta una variable de
entorno en su unidad systemd:

```ini
Environment=OPENCLAW_AGENT_ID=inmobiliaria-scraper
```

```bash
systemctl daemon-reload && systemctl restart openclaw-adaptador
```

## 4. Medir DESPUÉS y comprobar en el dashboard

```bash
openclaw agent --agent inmobiliaria-scraper --message "responde solo: ok" --json 2>&1 | tee /tmp/despues.json
```

Compara `cacheWrite` con el de `/tmp/antes.json`. **Objetivo: bajar de ~19.000 a
~4.000–6.000 tokens** (el contrato §5.4 son 2.930 de esos y no se puede quitar:
es lo que hace que la extracción valide).

Después, lanza **un** job real y mira la pantalla **Costes → Por job**. Ese número
es la verdad; los cálculos de esta guía son estimaciones.

---

## Lo que NO se ha hecho, y por qué

**Reutilizar la sesión entre jobs distintos** convertiría escrituras de caché
($2,50/M) en lecturas ($0,20/M) — 12,5× más barato en ese componente. Se
**descartó a propósito**: un job de Valencia que heredase contexto de uno de
Madrid podría colar datos cruzados en la extracción. Es exactamente el fallo
silencioso que el sistema existe para evitar. Se prefiere pagar más y que cada
job salga limpio.

**Bajar OpenClaw a Haiku** sin medir. Navegar y extraer es razonamiento agéntico:
un modelo más flojo puede necesitar más turnos y mandar más anuncios a cuarentena,
y salir más caro. Si se prueba, la métrica es **coste por anuncio válido**, no por
job.

---

## Sobre reutilizar sesión DENTRO del mismo job

Ya ocurre. El adaptador hace **una sola invocación** `openclaw agent` por job, con
**una sola** `--session-key` ([adaptador](../scripts/adaptador_openclaw_vps.py)),
así que todos los turnos de ese job comparten sesión y el preámbulo se escribe una
vez y se lee muchas. No hay nada que ganar ahí: ya está.

Lo que sí queda dentro del job es el **TTL de 5 minutos** de la caché. En un job
de 15 minutos con navegación lenta, la caché puede caducar varias veces y cada
caducidad reescribe todo el contexto acumulado. La aritmética:

| Estrategia | Coste del preámbulo |
|---|---|
| Caché 5 min, sin caducidades | 1 × 1,25 = **1,25×** |
| Caché 5 min, 2 caducidades | 3 × 1,25 = **3,75×** |
| Caché 1 hora | 1 × 2 = **2,00×** |

**El punto de equilibrio exacto:** 1h cuesta 2×; 5 min cuesta 1,25× por cada
escritura. `2 = 1,25 × N` → **N = 1,6**. Es decir, **la caché de 1 hora gana en
cuanto la de 5 minutos necesita 2 escrituras o más**. Si el job es rápido y nunca
caduca, 1h es PEOR (2× contra 1,25×).

### OpenClaw sí lo expone: `cacheRetention`

Verificado en <https://docs.openclaw.ai/reference/prompt-caching>. Valores:
`"none"`, `"short"` (5 min, el defecto) y `"long"` (1 hora, que se traduce a
`cache_control: {type: "ephemeral", ttl: "1h"}`). Ojo: `"standard"` **no** es
alias de `"short"`.

Tres sitios, de menos a más específico (el último gana):

1. `agents.defaults.params.cacheRetention`
2. `agents.defaults.models["proveedor/modelo"].params.cacheRetention`
3. `agents.entries[].params.cacheRetention`

```json5
{
  agents: {
    defaults: { params: { cacheRetention: "long" } },
    entries: {
      "inmobiliaria-scraper": {
        skills: [],
        params: { cacheRetention: "long" },
      },
    },
  },
}
```

**Condiciones que importan en nuestro caso:**

- Sobre `api.anthropic.com` (que es por donde va esto) hay soporte completo y
  siembra automática de `"short"` si no se toca nada.
- Por Bedrock o endpoints propios **hay que ponerlo explícito**: no hay siembra
  automática.
- La variable `OPENCLAW_CACHE_RETENTION=long` solo asciende a 1 hora en
  `api.anthropic.com` o Vertex; en otros hosts se queda en 5 minutos. Mejor
  ponerlo explícito en el JSON y no depender del entorno.
- Un valor inválido se ignora con un aviso — o sea, falla en silencio hacia el
  defecto. Compruébalo midiendo, no confiando.

### No lo actives a ciegas: ahora se puede medir

Esto ya no hay que estimarlo. El dashboard registra `cacheWrite` **por job**.
Lanza un job con la configuración actual (`short`) y mira **Costes → Por job**:

- Si `cacheWrite` ≈ el tamaño del preámbulo (una sola escritura), la caché no
  está caducando: **déjalo en `short`**, `long` te costaría más.
- Si `cacheWrite` ≈ 2× o más el preámbulo, está caducando varias veces:
  **cambia a `long`** y vuelve a medir.

Con el preámbulo ya podado la diferencia es menor en valor absoluto, pero la
regla no cambia. Podar primero, medir después, y decidir el TTL con el número
delante.
