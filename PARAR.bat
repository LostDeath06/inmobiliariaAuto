@echo off
REM ============================================================================
REM  PARAR.bat - Cierre limpio de lo que arranco ARRANCAR.bat
REM  Libera los puertos 8000 y 5173, cierra el worker (que no tiene puerto) por
REM  su linea de comando, cierra las ventanas sobrantes y (si lo pides) para la
REM  base de datos. Los datos se conservan siempre.
REM
REM  Defensivo a proposito: NO se fia solo del titulo de la ventana. En algunos
REM  arranques el cierre por titulo no alcanza al proceso hijo, asi que ademas
REM  mata por puerto (backend/frontend) y por linea de comando (worker).
REM ============================================================================
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title PARAR - Sourcing Inmobiliario

echo ============================================================
echo   PARADA - Sourcing Inmobiliario
echo ============================================================
echo.

echo [1/4] Liberando puertos del backend (8000) y frontend (5173)...
call :matar_puerto 8000 backend
call :matar_puerto 5173 frontend
echo.

echo [2/4] Cerrando el worker (no tiene puerto: se busca por linea de comando)...
powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process | ? { $_.Name -eq 'python.exe' -and $_.CommandLine -like '*backend.worker.worker*' }; if ($p) { $p | %% { Stop-Process $_.ProcessId -Force -ErrorAction SilentlyContinue }; exit 0 } else { exit 3 }"
if errorlevel 3 (
  echo       - worker no estaba en marcha.
) else (
  echo       - worker cerrado.
)
echo.

echo [3/4] Cerrando ventanas sobrantes BACKEND / WORKER / FRONTEND...
for %%T in (BACKEND WORKER FRONTEND) do (
  taskkill /FI "WINDOWTITLE eq %%T" /T /F >nul 2>&1
)
echo       - ventanas cerradas (si quedaba alguna abierta).
echo.

echo [4/4] Base de datos...
set "RESP=N"
set /p "RESP=Parar tambien Postgres? Los datos se conservan. [s/N]: "
if /I "!RESP!"=="S" (
  docker compose stop
  if not errorlevel 1 (
    echo       - Postgres detenido. Datos intactos; vuelve con ARRANCAR.bat.
  ) else (
    echo       - No se pudo parar la BD. Revisa que Docker responda.
  )
) else (
  echo       - BD intacta, sigue escuchando en el puerto 5455.
)

echo.
echo ============================================================
echo   Listo. Nada colgado.
echo ============================================================
pause
exit /b 0

REM --- subrutina: matar el proceso que escucha en un puerto -------------------
:matar_puerto
REM  %1 = puerto   %2 = etiqueta legible
set "PUERTO=%~1"
set "ETIQUETA=%~2"
set "ENCONTRADO="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PUERTO% .*LISTENING"') do (
  taskkill /PID %%P /F >nul 2>&1
  set "ENCONTRADO=1"
)
if defined ENCONTRADO (
  echo       - puerto %PUERTO% ^(%ETIQUETA%^) liberado.
) else (
  echo       - puerto %PUERTO% ^(%ETIQUETA%^) ya estaba libre.
)
exit /b 0
