@echo off
REM ============================================================================
REM  ARRANCAR.bat - Arranque defensivo del sistema (Sourcing Inmobiliario)
REM  Verifica cada paso antes del siguiente. Si algo falla, PARA y explica.
REM  Un arranque a medias (frontend vivo contra backend muerto) es peor que
REM  arrancar a mano, asi que no seguimos si un paso no queda verde.
REM ============================================================================
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title ARRANCAR - Sourcing Inmobiliario

echo ============================================================
echo   ARRANQUE - Sourcing Inmobiliario
echo ============================================================
echo.

REM --- 1. Prerrequisitos -----------------------------------------------------
echo [1/5] Comprobando prerrequisitos...

where docker >nul 2>&1
if errorlevel 1 (
  set "FALLO=Docker no esta en el PATH."
  set "ARREGLO=Instala Docker Desktop y abre de nuevo esta terminal."
  goto :error
)

where python >nul 2>&1
if errorlevel 1 (
  set "FALLO=Python no esta en el PATH."
  set "ARREGLO=Instala Python 3.11+ o ejecuta esto desde una terminal que lo tenga."
  goto :error
)

where npm >nul 2>&1
if errorlevel 1 (
  set "FALLO=npm no esta en el PATH."
  set "ARREGLO=Instala Node.js (incluye npm) y reabre la terminal."
  goto :error
)

docker info >nul 2>&1
if errorlevel 1 (
  set "FALLO=Docker esta instalado pero el daemon no responde."
  set "ARREGLO=Abre Docker Desktop, espera ~30s a que arranque y reintenta. En esta maquina Docker se cae a menudo."
  goto :error
)

if not exist ".env" (
  set "FALLO=No existe el fichero .env."
  set "ARREGLO=Ejecuta:  copy .env.example .env   y luego rellena ANTHROPIC_API_KEY. Ver ARRANQUE.md seccion 2."
  goto :error
)

findstr /R /C:"^DATABASE_URL=." .env >nul 2>&1
if errorlevel 1 (
  set "FALLO=DATABASE_URL esta vacia o ausente en .env."
  set "ARREGLO=Edita .env:  DATABASE_URL=postgresql://inmo:inmo@localhost:5455/inmobiliaria"
  goto :error
)

findstr /R /C:"^ANTHROPIC_API_KEY=." .env >nul 2>&1
if errorlevel 1 (
  set "FALLO=ANTHROPIC_API_KEY esta vacia o ausente en .env."
  set "ARREGLO=Edita .env y pon tu clave:  ANTHROPIC_API_KEY=sk-ant-...  (sin ella el analisis falla y todo sale NO_CALCULABLE)."
  goto :error
)

echo       OK - docker, python, npm, daemon y .env con claves.
echo.

REM --- 2. Base de datos: levantar y esperar a 'healthy' ----------------------
echo [2/5] Levantando Postgres y esperando a que este healthy...
docker compose up -d
if errorlevel 1 (
  set "FALLO=docker compose up fallo."
  set "ARREGLO=Lee el error de arriba. Si el daemon se cayo, reabre Docker Desktop y reintenta."
  goto :error
)

set /a intentos=0
:esperar_bd
set "SALUD="
for /f "delims=" %%H in ('docker inspect -f "{{.State.Health.Status}}" inmobiliaria_db 2^>nul') do set "SALUD=%%H"
if "!SALUD!"=="healthy" goto :bd_ok
docker info >nul 2>&1
if errorlevel 1 (
  set "FALLO=El daemon de Docker dejo de responder mientras esperaba la BD."
  set "ARREGLO=Reabre Docker Desktop, espera ~30s y vuelve a lanzar ARRANCAR.bat."
  goto :error
)
set /a intentos+=1
if !intentos! GEQ 30 (
  set "FALLO=Postgres no llego a 'healthy' tras ~60s (ultimo estado: !SALUD!)."
  set "ARREGLO=Revisa los logs:  docker compose logs postgres"
  goto :error
)
ping -n 3 127.0.0.1 >nul
goto :esperar_bd
:bd_ok
echo       OK - Postgres healthy en el puerto 5455.
echo.

REM --- 3. Migraciones + seeds (verificar que terminan bien) ------------------
echo [3/5] Aplicando migraciones y seeds...
python scripts\aplicar_migraciones.py
if errorlevel 1 (
  set "FALLO=Las migraciones fallaron."
  set "ARREGLO=Lee el error de arriba. Causa tipica: DATABASE_URL incorrecta o la BD aun no acepta conexiones."
  goto :error
)
echo       OK - esquema y seeds al dia.
echo.

REM --- 4. Servicios en ventanas propias -------------------------------------
echo [4/5] Abriendo BACKEND, WORKER y FRONTEND en ventanas separadas...
start "BACKEND"  cmd /k python -m uvicorn backend.main:app --port 8000
start "WORKER"   cmd /k python -m backend.worker.worker
start "FRONTEND" cmd /k npm --prefix frontend run dev
echo       Lanzados. Verificando que respondan de verdad...
echo.

REM --- 5. Comprobar que backend y frontend responden ------------------------
echo [5/5] Esperando al backend (http://localhost:8000/api/salud)...
set /a intentos=0
:esperar_api
powershell -NoProfile -Command "try{$r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 'http://localhost:8000/api/salud'; if($r.StatusCode -eq 200){exit 0}else{exit 1}}catch{exit 1}"
if not errorlevel 1 goto :api_ok
set /a intentos+=1
if !intentos! GEQ 40 (
  set "FALLO=El backend no respondio en ~90s."
  set "ARREGLO=Mira la ventana titulada BACKEND: ahi esta el traceback real de uvicorn (falta un paquete, .env mal, etc.)."
  goto :error
)
ping -n 3 127.0.0.1 >nul
goto :esperar_api
:api_ok
echo       OK - backend responde.

echo       Esperando al frontend (http://localhost:5173)...
set /a intentos=0
:esperar_front
powershell -NoProfile -Command "try{$r=Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 'http://localhost:5173/'; if($r.StatusCode -eq 200){exit 0}else{exit 1}}catch{exit 1}"
if not errorlevel 1 goto :front_ok
set /a intentos+=1
if !intentos! GEQ 40 (
  set "FALLO=El frontend no respondio en ~90s."
  set "ARREGLO=Mira la ventana titulada FRONTEND: revisa el error de Vite/npm (dependencias sin instalar? ejecuta 'npm install' en frontend)."
  goto :error
)
ping -n 3 127.0.0.1 >nul
goto :esperar_front
:front_ok
echo       OK - frontend sirve.
echo.

echo ============================================================
echo   TODO ARRIBA
echo ------------------------------------------------------------
echo   App    : http://localhost:5173      (se abre sola)
echo   Swagger: http://localhost:8000/docs  (NO se abre; abrela si la necesitas)
echo   Ventanas: BACKEND, WORKER, FRONTEND
echo   Para cerrarlo todo limpio:  PARAR.bat
echo ============================================================
start "" http://localhost:5173
echo.
echo (Puedes cerrar ESTA ventana; los servicios siguen en las suyas.)
pause
exit /b 0

:error
echo.
echo ############################################################
echo   ARRANQUE DETENIDO - no se ha dejado nada a medias.
echo ------------------------------------------------------------
echo   Fallo    : !FALLO!
echo   Que hacer: !ARREGLO!
echo ############################################################
echo.
pause
exit /b 1
