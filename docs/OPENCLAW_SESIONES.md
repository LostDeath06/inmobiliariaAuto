# Sesiones de OpenClaw: el gasto que el libro no veía, y cómo limpiarlo

> **El dato que lo destapó.** La sesión de chat `agent:main:main` estaba en
> **76.501 tokens de `cacheWrite` en un solo mensaje**, porque arrastraba 59
> mensajes de historial. A $2,50/millón eso son **~$0,19 cada vez que escribes**,
> y sube con cada mensaje. Nada de eso llegaba al dashboard de costes: el libro
> solo registraba el analista y los jobs de OpenClaw.

---

## 1. Por qué una sesión larga es cara

Una conversación no cobra "el mensaje que escribes": cobra **todo el contexto**
que hay que volver a poner delante del modelo. Con caché, ese contexto se escribe
una vez (a 1,25× la entrada) y se lee después (a 0,1×) — pero solo mientras la
caché no caduque.

La consecuencia práctica es contraintuitiva y conviene tenerla clara:

| Sesión | Coste aproximado por mensaje |
|---|---|
| Recién empezada | el preámbulo (system + skills) y poco más |
| 20 mensajes | preámbulo + 20 mensajes de historial |
| **59 mensajes** | **~76.500 tokens · ~$0,19** |
| 100 mensajes | más, y creciendo |

**No hay meseta.** Cada mensaje que añades encarece todos los siguientes. Por eso
el aviso del dashboard se dispara con `tokens_proximo_mensaje` (lo que costará el
siguiente) y no con el acumulado: el acumulado ya está gastado, lo otro todavía
se puede evitar.

Comparación con el resto del sistema, para dimensionar:

| | Coste |
|---|---|
| Analizar un inmueble entero | $0,0157 |
| Un mensaje en una sesión de 59 | **$0,19** |

**Un mensaje de chat cuesta 12 veces más que analizar un inmueble.**

---

## 2. Cómo lo captura ahora el sistema

OpenClaw deja cada sesión en `/root/.openclaw/agents/<agente>/sessions/*.jsonl`.

```
adaptador (host)  GET /sesiones   →  lee los .jsonl y agrega su `usage`
        ↓
worker (backend)  cada 5 min      →  anota SOLO el incremento en `uso_tokens`
        ↓
pantalla Costes                   →  fuente `OPENCLAW_CONVERSACION`, separada
```

Tres decisiones que importan:

- **Solo el incremento.** El `.jsonl` acumula: cada lectura ve el total de
  siempre. La tabla `sesiones_openclaw` guarda la última foto contabilizada y al
  libro va la diferencia. Sin eso, cada pasada del worker sumaría la sesión
  entera otra vez — 288 veces al día.
- **Las sesiones de job no se cuentan aquí.** Las que llevan
  `inmobiliaria:job:<id>` ya entran como gasto del job. Contarlas dos veces
  inflaría precisamente la cifra que existe para ser fiable.
- **Fuente separada.** `OPENCLAW_CONVERSACION` ≠ `OPENCLAW`. Mezclarlas
  escondería que charlar puede salir más caro que trabajar.

> **Lo que NO está verificado.** El formato interno de esos `.jsonl` no está
> documentado. El adaptador busca el bloque de consumo **por forma** (cualquier
> objeto con al menos dos de `input`/`output`/`cacheWrite`/`cacheRead`), igual
> que ya hace con el envoltorio de `--json`. Si el formato de tu instalación no
> encaja, la sesión llega con `formato_reconocido: false` y **no se inventa un
> cero**: la pantalla avisa de que el punto ciego sigue abierto. Compruébalo con
> el botón «Leer sesiones ahora» de la pantalla de Costes.

### Comprobar que funciona

```bash
curl -H "Authorization: Bearer TU_TOKEN" http://127.0.0.1:8080/sesiones | head -40
```

Si sale `"legible": false`, el servicio no puede leer la ruta: ajusta
`OPENCLAW_SESIONES_PATH` en la unidad systemd o revisa permisos. Mientras eso
esté así, el gasto de tus conversaciones **no se está contando** y la pantalla de
Costes lo dice en rojo.

---

## 3. Limpiar una sesión sin romper nada

Limpiar una sesión es **empezar una conversación nueva**. No borra el agente, ni
su configuración, ni sus skills, ni ninguna otra sesión. Lo único que se pierde
es el historial de esa conversación: el agente no recordará lo hablado.

### Opción A — la segura: abrir una sesión nueva y dejar la vieja

La más limpia porque **no borra nada**. Basta con usar otra clave de sesión:

```bash
openclaw agent --session-key "main:2026-07-24" --message "hola"
```

La sesión antigua queda en disco para consultarla, y deja de crecer. El coste por
mensaje vuelve al mínimo (solo el preámbulo).

Si quieres que sea el comportamiento por defecto de tu chat habitual, cambia la
clave que usas y no vuelvas a la vieja.

### Opción B — archivar el fichero

Si además quieres que el dashboard deje de contar esa sesión como activa:

```bash
# 1. Para el adaptador para que nadie lea a medias
sudo systemctl stop openclaw-adaptador

# 2. Comprueba que no hay ningún proceso de OpenClaw en marcha
pgrep -af openclaw

# 3. Archiva (NO borres a la primera: si algo va mal, se restaura)
cd /root/.openclaw/agents/main/sessions
mkdir -p ../sessions-archivo
mv agent-main-main.jsonl ../sessions-archivo/agent-main-main.$(date +%F).jsonl

# 4. Arranca
sudo systemctl start openclaw-adaptador
```

Al volver a leer, el adaptador ya no verá esa sesión. El gasto que **ya** estaba
anotado en `uso_tokens` **se conserva** (es contabilidad: no se reescribe el
pasado), pero deja de sumar.

### Qué pasa si vuelves a usar la misma clave después de limpiar

Está contemplado: el fichero nuevo será más pequeño que la foto guardada, así que
el delta saldría negativo. **No se anota nada en negativo** —nadie devuelve
dinero—, se acepta la foto nueva y se sigue contando desde ahí. Hay un test que
lo protege (`test_limpiar_una_sesion_no_genera_un_apunte_negativo`).

### Lo que NO hay que hacer

- **No borres `/root/.openclaw/agents/main/` entero.** Ahí vive la configuración
  del agente, no solo las sesiones.
- **No edites un `.jsonl` a mano** para "recortar" mensajes. Es un registro
  append-only; dejarlo a medias puede confundir al agente y al lector de costes.
  Abrir una sesión nueva consigue lo mismo sin riesgo.
- **No limpies con un job en marcha.** Para el adaptador primero.

---

## 4. El aviso automático

La pantalla de Costes marca en ámbar toda sesión cuyo **próximo mensaje** supere
el umbral (por defecto **50.000 tokens** ≈ $0,125 por mensaje). El umbral se
edita ahí mismo; se guarda en `config_app.umbral_tokens_sesion`, como todo
criterio configurable (Principio 2).

Cuando una sesión aparezca marcada, el arreglo es el de la sección 3: empezar
una nueva.

---

## Relación con el otro documento de coste

[`OPENCLAW_COSTES.md`](OPENCLAW_COSTES.md) trata el gasto de los **jobs**: podar
el preámbulo y elegir el TTL de caché. Este trata el gasto de **hablar** con el
agente. Son dos fuentes distintas y se optimizan distinto:

| | Job | Conversación |
|---|---|---|
| Sesión | una por job, se tira al acabar | una, crece sin límite |
| Palanca principal | podar el preámbulo (~73%) | **empezar sesión nueva** |
| Techo | acotado por job | ninguno: sube con cada mensaje |
