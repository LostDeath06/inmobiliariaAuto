#!/bin/sh
# =============================================================================
#  Genera el fichero de credenciales de nginx a partir del .env, al arrancar.
#  Si NO hay contraseña, el contenedor FALLA a propósito: es preferible que el
#  despliegue no arranque a que la app quede expuesta a internet sin credenciales.
# =============================================================================
set -e

: "${APP_USUARIO:=admin}"

if [ -z "${APP_PASSWORD}" ]; then
    echo "======================================================================" >&2
    echo " ERROR: APP_PASSWORD está vacía." >&2
    echo " La aplicación NO se expone sin contraseña." >&2
    echo " Edita el .env del VPS y pon:  APP_PASSWORD=una-contraseña-larga" >&2
    echo " Luego:  docker compose up -d --force-recreate frontend" >&2
    echo "======================================================================" >&2
    exit 1
fi

htpasswd -bc /etc/nginx/.htpasswd "${APP_USUARIO}" "${APP_PASSWORD}" >/dev/null 2>&1

# El entrypoint corre como root, pero los workers de nginx corren como el usuario
# `nginx`: sin darle lectura, nginx devuelve 500 (no 401) al validar credenciales.
# Grupo nginx + 640 => legible por nginx, no por el resto.
chown root:nginx /etc/nginx/.htpasswd
chmod 640 /etc/nginx/.htpasswd

echo "[auth] Autenticación básica activa. Usuario: ${APP_USUARIO}"

# --- Credencial de SOLO LECTURA (opcional) -----------------------------------
# Para el bot de consulta (OpenClaw/Telegram). Abre únicamente /api-lectura/,
# que nginx limita a GET/HEAD. Es una credencial aparte a propósito: la del bot
# no sirve para entrar en la app, y la de admin no hay que dársela al bot.
# Si no se configura, esa ruta simplemente no funciona y el resto sigue igual.
: "${CONSULTA_USUARIO:=consulta}"

if [ -n "${CONSULTA_PASSWORD}" ]; then
    htpasswd -bc /etc/nginx/.htpasswd_lectura "${CONSULTA_USUARIO}" "${CONSULTA_PASSWORD}" >/dev/null 2>&1
    chown root:nginx /etc/nginx/.htpasswd_lectura
    chmod 640 /etc/nginx/.htpasswd_lectura
    echo "[auth] Ruta de solo lectura /api-lectura/ activa. Usuario: ${CONSULTA_USUARIO}"
else
    echo "[auth] CONSULTA_PASSWORD vacía: /api-lectura/ queda deshabilitada (opcional)."
fi
