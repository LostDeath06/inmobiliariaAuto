# DESPLIEGUE — VPS Linux (Ubuntu 24.04 + Docker)

Procedimiento exacto para dejar el sistema corriendo 24/7 en el VPS, sin depender
de tu ordenador. Para el uso en local (Windows) sigue valiendo `ARRANQUE.md`.

> **Lo que NO cambia:** la lógica de negocio, el motor financiero, el scoring y los
> análisis están intactos. Esto es solo empaquetado y despliegue. 49 tests en verde.

---

## 0. Arquitectura del despliegue

```
                    Internet
                       │
                  :80  │  (única puerta; pide usuario y contraseña)
                       ▼
        ┌──────────────────────────────┐
        │  frontend  (nginx)           │
        │   · sirve el build de React  │
        │   · auth básica              │
        │   · proxy /api → backend     │
        └───────────────┬──────────────┘
                        │ red interna de Docker
        ┌───────────────┴──────────────┐
        │  backend (FastAPI/uvicorn)   │   ← sin puerto publicado
        └───────────────┬──────────────┘
                        │
        ┌───────────────┴──────────────┐     ┌────────────────────┐
        │  postgres  (127.0.0.1:5455)  │◄────┤ worker (APScheduler)│
        └──────────────────────────────┘     └────────────────────┘
                        ▲
              migraciones (one-shot: corre, termina, y solo
              entonces arranca el backend)
```

**Solo el frontend publica puerto.** El backend no es accesible desde internet: se
llega a la API únicamente a través del nginx, que exige contraseña. Postgres está
atado a `127.0.0.1` (solo desde el propio VPS o por túnel SSH).

### Por qué el worker va en un contenedor aparte y no dentro de la API

1. **Aislamiento de fallos.** Si el worker peta procesando un job, la API sigue
   sirviendo el ranking. Si fuesen el mismo proceso, se caerían juntos.
2. **Sin ticks duplicados.** El día que quieras más capacidad de API, escalas
   `backend` sin tocar `worker`. Si el scheduler viviera dentro de la API, cada
   réplica dispararía el mismo cron y ejecutarías cada búsqueda N veces.
3. **Logs y reinicios separados.** `docker compose logs worker` te da solo el cron;
   puedes reiniciar el worker sin cortar el tráfico web.
4. **Un proceso por contenedor**, que es como Docker espera que se haga.

Las tres piezas Python (API, worker, migraciones) comparten **la misma imagen** con
distinto `command`: un solo build y garantía de que corren el mismo código.

---

## 1. Preparar el `.env` en el VPS

```bash
cd ~/inmobiliariaAuto        # donde clonaste el repo
cp .env.example .env
nano .env
```

Rellena **como mínimo** esto:

| Variable | Qué poner | Por qué |
|---|---|---|
| `APP_PASSWORD` | Una contraseña larga tuya | **Obligatoria.** Sin ella el frontend no arranca (a propósito). |
| `APP_USUARIO` | `admin` o el que quieras | Usuario del login del navegador. |
| `ANTHROPIC_API_KEY` | Tu clave `sk-ant-...` | Sin ella el análisis falla y todo sale `NO_CALCULABLE`. |
| `POSTGRES_PASSWORD` | Cámbiala, no dejes `inmo` | Es un servidor real. |
| `COMPOSE_PROFILES=vps` | Descoméntala | Hace que `docker compose up -d` levante las 4 piezas. |
| `PUERTO_HTTP` | `80` | Puerto público. |

**No toques `DATABASE_URL`** en el VPS: docker compose la sobreescribe apuntando al
contenedor `postgres`. La que hay en el `.env` es para tu Windows.

---

## 2. Levantarlo (los comandos que ejecutas)

```bash
cd ~/inmobiliariaAuto
git pull
docker compose --profile vps up -d --build
```

Si pusiste `COMPOSE_PROFILES=vps` en el `.env`, basta con:

```bash
docker compose up -d --build
```

El arranque es en orden y está encadenado: `postgres` (espera a estar *healthy*) →
`migraciones` (corre y termina) → `backend` (no acepta tráfico hasta que las
migraciones acaban bien) → `frontend`.

---

## 3. Verificar que las cuatro piezas están vivas

```bash
docker compose --profile vps ps
```

Debes ver algo así (`migraciones` **no** aparece: es de un solo uso y ya terminó):

```
SERVICE    STATUS
postgres   Up (healthy)
backend    Up (healthy)
frontend   Up
worker     Up
```

Comprobaciones concretas:

```bash
# 1. La app pide contraseña (debe responder 401)
curl -s -o /dev/null -w "%{http_code}\n" http://localhost/

# 2. Con credenciales, la API responde (debe salir estado ok y base_datos true)
curl -s -u admin:TU_PASSWORD http://localhost/api/salud

# 3. Las migraciones se aplicaron
docker compose --profile vps logs migraciones | tail -20

# 4. El worker está haciendo tick
docker compose --profile vps logs --tail 5 worker
```

Y desde tu navegador: **`http://IP_DEL_VPS/`** → te pedirá usuario y contraseña.

---

## 4. Ver logs si algo falla

```bash
docker compose --profile vps logs -f            # todo, en vivo
docker compose --profile vps logs -f backend    # solo la API
docker compose --profile vps logs -f worker     # solo el cron
docker compose --profile vps logs frontend      # nginx (incluye errores de auth)
docker compose --profile vps logs migraciones   # por qué no arrancó el backend
```

Diagnóstico rápido de los fallos más probables:

| Síntoma | Causa casi segura | Arreglo |
|---|---|---|
| `frontend` se reinicia en bucle | `APP_PASSWORD` vacía | Rellénala en `.env` y `docker compose up -d --force-recreate frontend` |
| `[emerg] host not found in upstream "backend"` | Versión antigua del `nginx.conf`: nginx resolvía el backend al arrancar y moría si aún no existía | Ya corregido (resolución diferida con el DNS de Docker). Asegúrate de traerlo con `git pull` y **reconstruir**: `docker compose --profile vps up -d --build frontend` |
| `/api` devuelve 502 pero la web carga | El backend está caído o aún arrancando | `docker compose --profile vps logs backend`. nginx se reengancha solo en cuanto vuelva; no hace falta reiniciarlo |
| `backend` no arranca | `migraciones` falló | `docker compose logs migraciones` y mira el error de SQL/conexión |
| Web carga pero sin datos | Falta `ANTHROPIC_API_KEY`, o no hay inmuebles | Ver "Estado por país" en la app |
| El navegador no conecta | Cortafuegos del VPS | `sudo ufw allow 80/tcp` |

---

## 5. Parar, reiniciar, actualizar

```bash
# Parar todo (los datos se conservan en el volumen)
docker compose --profile vps down

# Reiniciar una pieza suelta
docker compose --profile vps restart backend

# Aplicar cambios de código traídos con git pull
git pull && docker compose --profile vps up -d --build

# Cambiar la contraseña de acceso
nano .env                                                  # edita APP_PASSWORD
docker compose up -d --force-recreate frontend
```

Todo lleva `restart: unless-stopped`: **si el VPS se reinicia, el sistema vuelve
solo**, sin que tengas que entrar por SSH.

---

## 6. Conectar OpenClaw (adaptador + activación)

OpenClaw corre en el **host** (fuera de Docker) con su Gateway en
`ws://127.0.0.1:18789`. El backend no lo invoca directamente: entre medias va el
**adaptador** (`scripts/adaptador_openclaw_vps.py`), un servicio HTTP que traduce
cada job a una ejecución real del agente.

### 6.1 Cómo se invoca OpenClaw (y por qué así)

El adaptador usa el **CLI**: `openclaw agent --message-file … --json --timeout …`,
que la documentación describe como *"runs a single agent turn through the Gateway…
executes non-interactively to completion, then returns results to stdout"*.

Se eligió frente a hablar el WebSocket del Gateway (`chat.send`) porque:
- Está pensado literalmente para ejecución no interactiva hasta completar.
- Separa stdout de stderr, para que un script pueda parsear stdout directamente.
- Trae `--timeout` propio, y `--message-file` evita límites de longitud de
  argumento con prompts largos.
- Pasa igualmente por el Gateway, pero absorbe el handshake y el versionado del
  protocolo. Hacerlo a mano obligaría a seguir el stream de eventos y a depender
  de la forma exacta de `session.operation`, **que la documentación pública no
  detalla**. Menos superficie que se rompa.

### 6.2 El system prompt del contrato: se inyecta en cada llamada

No hay que pegarlo en la configuración de OpenClaw. El adaptador **lee
`docs/PROMPT_PARA_OPENCLAW.md` y lo antepone al prompt de cada job**. Así el
contrato viaja versionado con el repo: si cambia el formato de salida, basta un
`git pull` y no hay riesgo de que la config del VPS quede desincronizada.

### 6.3 Instalar el adaptador como servicio

```bash
# 1. Dependencias (en el host, fuera de Docker)
sudo apt update && sudo apt install -y python3-pip
sudo pip3 install --break-system-packages fastapi uvicorn

# 2. Comprobar que el CLI está y responde
which openclaw && openclaw --version

# 3. Ver el envoltorio REAL que devuelve --json en TU instalación
cd /root/inmobiliariaAuto/scripts
python3 adaptador_openclaw_vps.py --sonda "responde solo con {\"ok\":true}"

# 4. Instalar la unidad systemd
sudo cp openclaw-adaptador.service /etc/systemd/system/
sudo nano /etc/systemd/system/openclaw-adaptador.service   # pon OPENCLAW_API_KEY
#   Revisa también OPENCLAW_ESTADO_PATH (estado que sobrevive al reinicio) y
#   OPENCLAW_SESIONES_PATH (gasto de las conversaciones, ver docs/OPENCLAW_SESIONES.md)
sudo systemctl daemon-reload
sudo systemctl enable --now openclaw-adaptador
systemctl status openclaw-adaptador

# 5. Comprobar
curl -H "Authorization: Bearer TU_TOKEN" http://127.0.0.1:8080/health
```

El paso 3 importa: **el esquema del envoltorio de `--json` no está documentado**.
El adaptador no asume ninguna clave (busca el objeto del contrato §5.4 venga plano,
anidado o dentro de un bloque markdown), pero la sonda te enseña la forma real por
si hiciera falta ajustar algo.

### 6.4 Seguridad del puerto 8080

El adaptador escucha en `0.0.0.0:8080` **porque el backend vive en Docker** y entra
por `host.docker.internal`; con `127.0.0.1` el contenedor no llegaría. Eso lo deja
alcanzable desde fuera, así que **ciérralo en el cortafuegos**:

```bash
sudo ufw deny 8080/tcp        # nadie desde internet
sudo ufw allow from 172.16.0.0/12 to any port 8080 proto tcp   # solo redes Docker
sudo ufw status
```

Además el adaptador exige `Authorization: Bearer <OPENCLAW_API_KEY>` si la defines
(hazlo), y debe coincidir con la del `.env` del backend.

### 6.5 Activar el modo http en el backend

```bash
cd /root/inmobiliariaAuto
nano .env
#   OPENCLAW_MODE=http
#   OPENCLAW_BASE_URL=http://host.docker.internal:8080
#   OPENCLAW_API_KEY=el-mismo-token-del-servicio
docker compose --profile vps up -d --force-recreate backend worker
```

> **El matiz de red:** dentro de un contenedor `localhost` es el **propio
> contenedor**, no el VPS. Como OpenClaw y el adaptador corren en el host, la
> dirección correcta es `host.docker.internal`, ya cableada en
> `docker-compose.yml` con `extra_hosts: host-gateway`. **Este montaje sigue siendo
> el correcto.** Si algún día metes OpenClaw como servicio del compose, cambia a
> `http://openclaw:8080`.

Comprobación final: `curl -u admin:TU_PASSWORD http://localhost/api/salud` debe
mostrar `"openclaw": {"modo": "http", "disponible": true}`. A partir de ahí, el
worker despacha las búsquedas con cron y el ciclo se cierra solo.

### 6.6 Si un job falla

```bash
journalctl -u openclaw-adaptador -f          # qué pasó en el adaptador
curl -H "Authorization: Bearer TU_TOKEN" http://127.0.0.1:8080/jobs/<job_id>
```

El adaptador **nunca inventa datos**: si OpenClaw sale con error, si la salida no
trae el JSON del contrato o si no valida contra §5.4, el job queda `FALLIDO` con el
motivo y `resultado` vacío. En la app lo verás en el Monitor.

### 6.7 Cancelar un job en curso

Desde la app: **Monitor → Cancelar**, con confirmación. Aborta el proceso de
OpenClaw (y sus hijos) y anota el gasto ya consumido en el libro de costes.

Si el aviso dice que el adaptador **no confirmó** que el proceso muriera, no es
retórica: compruébalo, porque puede seguir gastando.

```bash
pgrep -af openclaw                 # ¿queda algún proceso vivo?
sudo pkill -f "openclaw agent"     # solo si sigue ahí tras cancelar
```

También por API, si prefieres la terminal:

```bash
curl -u admin:TU_PASSWORD -X POST http://localhost/api/jobs/<job_id>/cancelar
```

### 6.8 Jobs zombis (reinicio del adaptador)

El adaptador guarda sus jobs **en memoria**. Antes, un `systemctl restart` los
perdía y el backend —que los tenía como `EN_PROGRESO`— los sondeaba para siempre,
recibiendo `404 Not Found` cada pocos segundos.

Eso ya no ocurre, por tres vías independientes:

1. El adaptador **persiste su estado** en `OPENCLAW_ESTADO_PATH` y, al arrancar,
   cierra como `FALLIDO` los jobs que estaban vivos, con el motivo real (su
   proceso murió con el servicio). Si no encuentra el fichero, lo avisa en el log.
2. El backend **se rinde tras 5 consultas seguidas con 404**
   (`config_app.max_sondeos_no_encontrado`) y marca el job `FALLIDO`.
3. Hay un **timeout duro**: `OPENCLAW_TIMEOUT_SEGUNDOS` + 60 s del adaptador +
   `config_app.margen_timeout_job_segundos`. Ningún job puede quedar
   `EN_PROGRESO` indefinidamente, conteste el adaptador o no.

**Limpiar los zombis que ya existen** (los anteriores a este cambio):

```bash
curl -u admin:TU_PASSWORD -X POST "http://localhost/api/jobs/limpiar-zombis?minutos=60"
```

O desde la app: **Monitor → Jobs zombis → Cerrar jobs de más de 60 min**.

Si prefieres hacerlo en la base de datos, el equivalente:

```sql
UPDATE jobs SET estado = 'FALLIDO', finalizado_en = now(),
       error_mensaje = 'Cerrado a mano: el adaptador no reconoce el job (reinicio).'
WHERE estado IN ('PENDIENTE','ENVIADO','EN_PROGRESO')
  AND COALESCE(iniciado_en, created_at) < now() - INTERVAL '60 minutes';
```

---

## 7. Seguridad — qué protege y qué no

**Lo que hay:**
- Contraseña (auth básica de nginx) sobre **toda** la app: web, API y `/docs`.
- Backend y Postgres **sin puertos publicados** a internet.
- El frontend **se niega a arrancar** si no hay contraseña.
- Contenedores del backend corriendo como usuario no-root.

**Lo que NO hay, y deberías saber:**
- **Sin HTTPS.** Con `http://` la contraseña viaja en claro. Es aceptable para
  probar desde tu red, pero **antes de usarlo en serio pon un dominio y TLS**
  (tu plantilla de Hostinger ya trae Traefik, que lo hace con Let's Encrypt).
- Sigue siendo **mono-usuario**: una sola contraseña, sin roles ni usuarios.
- La política RLS de la base sigue permisiva; la barrera real es el nginx.

---

## 8. Flujo completo: de tu ordenador al VPS

Confirmado, es exactamente lo que planteas:

**En tu Windows (una vez):**
```bash
git add -A
git commit -m "Despliegue en VPS con Docker"
git push
```

**En el VPS (cada vez que actualices):**
```bash
cd ~/inmobiliariaAuto
git pull
docker compose --profile vps up -d --build
```

`--build` es importante: sin él Docker reutiliza la imagen antigua y tus cambios de
código no entran. Los datos de Postgres viven en un volumen y **no se pierden** al
reconstruir.

Nota: el `.env` **no** viaja por git (está en `.gitignore`, y así debe seguir). El
del VPS lo mantienes tú allí; cuando añada variables nuevas, compara con
`.env.example` tras cada `git pull`.
