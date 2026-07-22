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

## 6. Activar OpenClaw cuando lo montes (aún NO)

Hoy está en `OPENCLAW_MODE=manual`. Cuando OpenClaw esté vivo en el VPS:

```bash
nano .env
#   OPENCLAW_MODE=http
#   OPENCLAW_BASE_URL=http://host.docker.internal:8080     ← ajusta el puerto
#   OPENCLAW_API_KEY=...                                    ← si tu adaptador lo exige
docker compose up -d --force-recreate backend worker
```

> **El matiz que rompe esto si no lo sabes:** dentro de un contenedor, `localhost`
> es el **propio contenedor**, no el VPS. Si OpenClaw corre en el host (fuera de
> Docker), la dirección correcta es `host.docker.internal`, ya cableada en
> `docker-compose.yml` con `extra_hosts`. Si en cambio metes OpenClaw como un
> servicio más del compose, usa el nombre del servicio (`http://openclaw:8080`).

Comprobación: `curl -u admin:TU_PASSWORD http://localhost/api/salud` debe mostrar
`"openclaw": {"modo": "http", "disponible": true}`.

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
