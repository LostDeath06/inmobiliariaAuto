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
