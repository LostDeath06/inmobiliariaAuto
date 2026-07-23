# Consultar el sistema por Telegram (OpenClaw, solo lectura)

Permite preguntarle a OpenClaw por Telegram cosas como *"¿cuál es el top 5 del
ranking de España?"* o *"¿qué me falta para que Venezuela sea operativo?"*, y que
responda con **datos reales** de la API, no con suposiciones.

> **Solo lectura.** Por esta vía no se puede crear búsquedas, borrar inmuebles,
> cambiar configuración ni lanzar jobs. No es solo una norma escrita en la skill:
> nginx rechaza cualquier método que no sea `GET`/`HEAD` en la ruta que usa el bot.

---

## 0. Antes de empezar: cómo encaja

```
Telegram  ──►  OpenClaw (host del VPS, /root/.openclaw)
                   │  skill inmobiliaria-consulta
                   │  ejecuta consultar.sh (curl)
                   ▼
              nginx :80  /api-lectura/   ← credencial propia + SOLO GET/HEAD
                   │
                   ▼
              backend (Docker, sin puerto publicado)
```

**Corrección importante sobre un supuesto habitual:** el backend **no publica el
puerto 8000**. Desde el host del VPS, `http://localhost:8000` no existe: solo se
llega a la API a través de nginx. Por eso la skill apunta a
`http://localhost/api-lectura`, no a `localhost:8000`.

---

## 1. Crear la credencial de solo lectura

En el VPS, edita el `.env`:

```bash
cd /root/inmobiliariaAuto
openssl rand -base64 32          # copia el resultado
nano .env
```

Añade (o rellena) estas dos líneas:

```
CONSULTA_USUARIO=consulta
CONSULTA_PASSWORD=<lo-que-generó-openssl>
```

Es **distinta** de `APP_PASSWORD` a propósito: la del bot no abre la aplicación
web, y la de admin no hay que dársela al bot.

## 2. Validar la configuración de nginx ANTES de desplegar

Un `nginx.conf` inválido deja el sitio caído. Compruébalo sin tocar el stack:

```bash
docker run --rm -v /root/inmobiliariaAuto/frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro nginx:alpine nginx -t
```

Debe decir `syntax is ok` / `test is successful`. Si falla, **no despliegues**.

## 3. Desplegar

```bash
cd /root/inmobiliariaAuto && git pull && docker compose --profile vps up -d --build
```

En los logs del frontend debe aparecer:

```bash
docker compose logs frontend | grep '\[auth\]'
```
```
[auth] Autenticación básica activa. Usuario: admin
[auth] Ruta de solo lectura /api-lectura/ activa. Usuario: consulta
```

## 4. Comprobar que la barrera de solo lectura funciona

Esto es lo que **no** hay que saltarse. Cuatro comprobaciones:

```bash
# 1) La consulta funciona (debe devolver JSON)
curl -s -u consulta:TU_CLAVE http://localhost/api-lectura/salud

# 2) Escribir está prohibido (debe devolver 403)
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
     -u consulta:TU_CLAVE http://localhost/api-lectura/pipeline/recalcular-todo

# 3) La credencial del bot NO abre la app ni la API de escritura (debe dar 401)
curl -s -o /dev/null -w '%{http_code}\n' -u consulta:TU_CLAVE http://localhost/api/perfiles

# 4) Sin credenciales, nada (debe dar 401)
curl -s -o /dev/null -w '%{http_code}\n' http://localhost/api-lectura/salud
```

Esperado: `JSON`, `403`, `401`, `401`. Si el 2 no da 403, **para y revisa** antes
de conectar Telegram.

## 5. Instalar la skill en OpenClaw

La skill vive versionada en el repo, así que ya está en el VPS tras el `git pull`:

```bash
openclaw skills install /root/inmobiliariaAuto/openclaw/skills/inmobiliaria-consulta --as inmobiliaria-consulta
chmod +x /root/inmobiliariaAuto/openclaw/skills/inmobiliaria-consulta/consultar.sh
openclaw skills list      # debe aparecer "inmobiliaria-consulta"
```

Si prefieres que la vean todos los agentes, añade `--global`.

Cuando actualices el repo, refresca la skill:

```bash
openclaw skills update --all
```

## 6. Inyectar las credenciales (nunca en el código)

Las credenciales van en la configuración de OpenClaw, **no** en la skill ni en el
script. Edita `/root/.openclaw/openclaw.json`:

```json5
{
  skills: {
    entries: {
      "inmobiliaria-consulta": {
        env: {
          INMO_API_BASE: "http://localhost/api-lectura",
          INMO_CONSULTA_USUARIO: "consulta",
          INMO_CONSULTA_PASSWORD: "<la misma de CONSULTA_PASSWORD>",
        },
      },
    },
  },
}
```

Protege el fichero, que ahora contiene un secreto:

```bash
chmod 600 /root/.openclaw/openclaw.json
```

> Alternativa si prefieres no duplicar el secreto: exporta las tres variables en
> el `systemd` del proceso de OpenClaw (`Environment=` o `EnvironmentFile=`) y
> deja fuera el bloque `env`. La skill declara en su frontmatter qué variables
> necesita (`metadata.openclaw.requires.env`), pero **no** las inventa: si no
> están, el script aborta con un error claro en vez de responder a medias.

## 7. Conectar Telegram

Crea un bot con **@BotFather** en Telegram y copia el token. Después, en
`/root/.openclaw/openclaw.json`:

```json5
{
  channels: {
    telegram: {
      enabled: true,
      botToken: "123456:ABC-DEF...",
      dmPolicy: "allowlist",
    },
  },
}
```

**Usa `allowlist` con tu ID numérico de Telegram, no `open`.** Este bot habla con
un agente que corre como `root` en tu VPS y tiene herramienta de ejecución de
comandos: quien pueda escribirle tiene mucha más superficie que el ranking. El ID
lo da cualquier bot tipo *userinfo*; también puedes dejar `dmPolicy: "pairing"`
(el valor por defecto), que exige aprobar cada nuevo contacto.

Reinicia OpenClaw para que tome la configuración.

## 8. Probar

Primero por línea de comandos, que aísla el problema si algo falla:

```bash
cd /root/inmobiliariaAuto/openclaw/skills/inmobiliaria-consulta
export INMO_API_BASE=http://localhost/api-lectura
export INMO_CONSULTA_USUARIO=consulta
export INMO_CONSULTA_PASSWORD=TU_CLAVE

./consultar.sh salud
./consultar.sh inventario
./consultar.sh ranking ES --limite 5
./consultar.sh estado-pais VE
./consultar.sh jobs
```

Si eso responde, prueba en Telegram:

- «¿Cuál es el top 5 del ranking de España?»
- «¿Cuántos inmuebles hay por país?»
- «Resúmeme los pisos con score mayor a 60»
- «¿Qué configuración me falta para que Venezuela sea operativo?»
- «¿Hay algún job fallido y por qué?»

Y comprueba que se niega a escribir:

- «Crea una búsqueda en Valencia por 200.000 €» → debe explicar que la consulta
  por chat es de solo lectura y remitirte a la aplicación web.

---

## Qué cubre cada capa (y qué no)

| Capa | Qué impide | ¿Es una barrera real? |
|---|---|---|
| Texto de `SKILL.md` | Que el agente *intente* escribir | **No.** Son instrucciones; un modelo puede ignorarlas |
| `consultar.sh` | Rutas arbitrarias; solo hace `curl --get` | **No.** El agente tiene `exec` y podría llamar a curl por su cuenta |
| **nginx `/api-lectura/`** | **Todo lo que no sea GET/HEAD (403)** | **Sí.** Corta antes de llegar al backend |
| **Credencial separada** | Que el bot use la API de escritura (401) | **Sí** |

Por eso el paso 4 no es opcional: es el único que comprueba lo que de verdad
sostiene la promesa de "solo lectura".

## Limitaciones conocidas

- **OpenClaw corre como `root` y tiene herramienta de ejecución de comandos.**
  Puede leer el `.env` del repo, donde está `APP_PASSWORD`. La separación de
  credenciales evita el acceso *accidental* por la skill, no protege frente a
  quien controle el chat. De ahí la insistencia en `dmPolicy`.
- **Sin TLS extremo a extremo** dentro del VPS: la llamada del bot a
  `http://localhost/api-lectura` no va cifrada. No sale de la máquina, pero
  conviene saberlo (`resumen.md` §7.3).
- **`limit_except` filtra por método, no por endpoint.** Un `GET` a cualquier
  ruta de lectura de la API es posible desde esa credencial, aunque el script
  solo exponga unas pocas. Ningún `GET` de esta API modifica estado.
- El bloque `metadata.openclaw.requires` del frontmatter sigue lo documentado en
  <https://docs.openclaw.ai/tools/skills>. Si tu versión de OpenClaw lo ignorase,
  la skill funciona igual siempre que las variables de entorno estén inyectadas:
  ese bloque solo sirve para que OpenClaw avise si falta algo.
