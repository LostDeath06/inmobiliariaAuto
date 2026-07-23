#!/usr/bin/env bash
# =============================================================================
#  Consulta de SOLO LECTURA del sistema de sourcing inmobiliario.
#
#  Este script es comodidad, NO seguridad. La barrera real está en nginx: la
#  credencial que usa aquí solo abre /api-lectura/, y esa ruta está limitada a
#  GET/HEAD con `limit_except`. Aunque alguien invocara curl a mano con estas
#  credenciales, un POST devuelve 403 sin llegar al backend.
#
#  Aquí, además: lista blanca de subcomandos (nunca una ruta arbitraria) y
#  siempre `curl --get`.
#
#  Variables de entorno (las inyecta OpenClaw, ver SKILL.md):
#    INMO_API_BASE            p.ej. http://localhost/api-lectura
#    INMO_CONSULTA_USUARIO    usuario de la credencial de solo lectura
#    INMO_CONSULTA_PASSWORD   su contraseña
# =============================================================================
set -euo pipefail

AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FORMATEAR="${AQUI}/formatear.py"

BASE="${INMO_API_BASE:-http://localhost/api-lectura}"
BASE="${BASE%/}"
USUARIO="${INMO_CONSULTA_USUARIO:-}"
CLAVE="${INMO_CONSULTA_PASSWORD:-}"

if [ -z "$USUARIO" ] || [ -z "$CLAVE" ]; then
    echo "ERROR: faltan INMO_CONSULTA_USUARIO / INMO_CONSULTA_PASSWORD." >&2
    echo "Configúralas en openclaw.json, en skills.entries.inmobiliaria-consulta.env" >&2
    exit 2
fi

# --- GET, y solo GET ---------------------------------------------------------
_get() {
    local ruta="$1"; shift
    curl --get --silent --show-error --fail-with-body --max-time 30 \
         --user "${USUARIO}:${CLAVE}" \
         "${BASE}${ruta}" "$@"
}

_uuid_valido() {
    printf '%s' "${1:-}" | grep -Eq '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
}

# Resuelve un perfil por nombre parcial; acepta un UUID tal cual; por defecto,
# el perfil predeterminado del sistema.
_perfil_id() {
    local buscado="${1:-}"
    if _uuid_valido "$buscado"; then
        printf '%s' "$buscado"
        return
    fi
    _get "/perfiles" | python3 "$FORMATEAR" perfil-id --buscado "$buscado"
}

uso() {
    cat <<'AYUDA'
Subcomandos (todos de solo lectura):

  perfiles                       Perfiles de inversor disponibles
  ranking [PAIS] [opciones]      Top del ranking. PAIS: ES | DO | VE | global
       --perfil <texto|uuid>       perfil de inversor (por defecto, el predeterminado)
       --limite <n>                cuántos devolver (por defecto 10)
       --bruto                     usar el score bruto, sin el multiplicador de riesgo país
  inmueble <uuid>                Ficha completa de un inmueble
  historico <uuid>               Histórico de precios de un inmueble
  inventario                     Recuento de inmuebles por país y ciudad
  estado-pais [PAIS]             Qué falta para que un país sea operativo
  jobs                           Estado de los jobs, con el motivo de los fallidos
  senales-fuera-catalogo         Inmuebles cuyas señales el catálogo ignoró
  salud                          ¿Está viva la API?
AYUDA
}

comando="${1:-}"
[ $# -gt 0 ] && shift

case "$comando" in

  perfiles)
    _get "/perfiles" | python3 "$FORMATEAR" perfiles
    ;;

  ranking)
    pais=""; perfil=""; limite="10"; bruto="false"
    while [ $# -gt 0 ]; do
      case "$1" in
        --perfil) perfil="${2:-}"; shift 2 ;;
        --limite) limite="${2:-10}"; shift 2 ;;
        --bruto)  bruto="true"; shift ;;
        ES|DO|VE|es|do|ve) pais=$(printf '%s' "$1" | tr '[:lower:]' '[:upper:]'); shift ;;
        global|GLOBAL|Global) pais=""; shift ;;
        *) echo "Argumento no reconocido en 'ranking': $1" >&2; exit 2 ;;
      esac
    done
    printf '%s' "$limite" | grep -Eq '^[0-9]{1,3}$' || { echo "--limite debe ser un número de 1 a 3 dígitos." >&2; exit 2; }
    pid="$(_perfil_id "$perfil")"
    args=(--data-urlencode "perfil_id=${pid}"
          --data-urlencode "limit=${limite}"
          --data-urlencode "sin_riesgo_pais=${bruto}")
    [ -n "$pais" ] && args+=(--data-urlencode "pais=${pais}")
    _get "/ranking" "${args[@]}" | python3 "$FORMATEAR" ranking --bruto "$bruto"
    ;;

  inmueble)
    _uuid_valido "${1:-}" || { echo "Pasa un UUID de inmueble válido." >&2; exit 2; }
    _get "/inmuebles/$1" | python3 "$FORMATEAR" inmueble
    ;;

  historico)
    _uuid_valido "${1:-}" || { echo "Pasa un UUID de inmueble válido." >&2; exit 2; }
    _get "/inmuebles/$1/historico-precios" | python3 "$FORMATEAR" historico
    ;;

  inventario)
    _get "/inmuebles" --data-urlencode "limit=1000" | python3 "$FORMATEAR" inventario
    ;;

  estado-pais)
    ruta="/config/estado-pais"
    if [ -n "${1:-}" ]; then
      p=$(printf '%s' "$1" | tr '[:lower:]' '[:upper:]')
      printf '%s' "$p" | grep -Eq '^(ES|DO|VE)$' || { echo "País no reconocido: $1 (usa ES, DO o VE)." >&2; exit 2; }
      ruta="/config/estado-pais/${p}"
    fi
    _get "$ruta" | python3 "$FORMATEAR" estado-pais
    ;;

  jobs)
    _get "/jobs" | python3 "$FORMATEAR" jobs
    ;;

  senales-fuera-catalogo)
    _get "/senales-no-reconocidas" | python3 "$FORMATEAR" senales
    ;;

  salud)
    _get "/salud" | python3 "$FORMATEAR" salud
    ;;

  ""|-h|--help|ayuda)
    uso
    ;;

  *)
    echo "Subcomando desconocido: ${comando}" >&2
    echo >&2
    uso >&2
    exit 2
    ;;
esac
